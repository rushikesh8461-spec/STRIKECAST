"""
Multimodal fusion model (Phase 8).

PLACEHOLDER architecture — modalities and per-modality channel counts come
from DataContract.modalities / modality_channels, which are themselves
unconfirmed pending M1/M2. Do not treat the specific modality list here as
final; this is built to be generic over whatever DataContract declares.

Architecture:
    modality_1 -> ConvLSTM encoder -> final hidden state [B, hidden, H, W] ┐
    modality_2 -> ConvLSTM encoder -> final hidden state [B, hidden, H, W] ┤
    ...                                                                    ┤-> concat (channel dim)
    modality_N -> ConvLSTM encoder -> final hidden state [B, hidden, H, W] ┘
                                                                             |
                                                                        1x1 conv fusion
                                                                             |
                                                                      prediction head
                                                                             |
                                                                [B, T_out, C_out, H, W]

Each modality gets its own encoder (not shared weights) since different
modalities (e.g. radar vs satellite) have different input channel counts
and statistics. Fusion is a simple channel-concat + 1x1 conv rather than
attention/transformer fusion — kept deliberately simple per Phase 9
(transformer fusion is explicitly out of MVP scope).
"""

from typing import Dict
import torch
import torch.nn as nn

from src.models.base import BaseForecastNNModel
from src.models.convlstm_cell import ConvLSTMCell
from ml.training.strikecast_training.config import DataContract


class _ModalityEncoder(nn.Module):
    """Runs a small ConvLSTM stack over one modality's sequence and returns
    only the final hidden state (used as that modality's feature map)."""

    def __init__(self, input_channels: int, hidden_dims, kernel_size: int = 3):
        super().__init__()
        cells = []
        for i, hdim in enumerate(hidden_dims):
            in_ch = input_channels if i == 0 else hidden_dims[i - 1]
            cells.append(ConvLSTMCell(in_ch, hdim, kernel_size))
        self.cells = nn.ModuleList(cells)
        self.out_channels = hidden_dims[-1]

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: [B,T,C,H,W] -> [B, hidden_dims[-1], H, W]"""
        B, T, C, H, W = x.shape
        device, dtype = x.device, x.dtype
        states = [cell.init_hidden(B, H, W, device, dtype) for cell in self.cells]

        for t in range(T):
            layer_input = x[:, t, :, :, :]
            for i, cell in enumerate(self.cells):
                h_prev, c_prev = states[i]
                h_next, c_next = cell(layer_input, h_prev, c_prev)
                states[i] = (h_next, c_next)
                layer_input = h_next

        return states[-1][0]  # final hidden state of last layer


class FusionConvLSTM(BaseForecastNNModel):
    model_name = "fusion_convlstm"
    model_version = "0.1.0"

    def __init__(self, contract: DataContract, encoder_hidden_dims=None, kernel_size: int = 3):
        super().__init__(contract)
        if len(contract.modalities) < 2:
            raise ValueError(
                "FusionConvLSTM requires DataContract.modalities to have "
                "at least 2 entries. For single-modality data, use ConvLSTM "
                "directly instead of fusion."
            )
        encoder_hidden_dims = encoder_hidden_dims or [16, 16]

        self.encoders = nn.ModuleDict({
            m: _ModalityEncoder(contract.modality_channels[m], encoder_hidden_dims, kernel_size)
            for m in contract.modalities
        })

        fused_channels = encoder_hidden_dims[-1] * len(contract.modalities)
        self.fusion_conv = nn.Conv2d(fused_channels, encoder_hidden_dims[-1], kernel_size=1)

        c_out = contract.num_classes if contract.target_type == "multiclass" else 1
        self._c_out = c_out
        self.head = nn.Conv2d(
            encoder_hidden_dims[-1], contract.forecast_horizon * c_out, kernel_size=1
        )

    def forward(self, x: Dict[str, torch.Tensor]) -> torch.Tensor:
        """x: dict[modality_name] -> [B,T,C_m,H,W]. All modalities must
        share the same B, T, H, W (only C differs)."""
        if not isinstance(x, dict):
            raise TypeError(
                "FusionConvLSTM expects a dict[str, Tensor] input (one "
                "tensor per modality), matching DataContract.modalities. "
                "Got a single Tensor — use ConvLSTM for single-modality input."
            )

        encoded = [self.encoders[m](x[m]) for m in self.contract.modalities]
        fused = torch.cat(encoded, dim=1)  # [B, sum(hidden), H, W]
        fused = torch.relu(self.fusion_conv(fused))  # [B, hidden, H, W]

        B, _, H, W = fused.shape
        out = self.head(fused)  # [B, T_out*C_out, H, W]
        T_out = self.contract.forecast_horizon
        out = out.view(B, T_out, self._c_out, H, W)

        if self.contract.target_type == "binary":
            out = torch.sigmoid(out)

        return out
