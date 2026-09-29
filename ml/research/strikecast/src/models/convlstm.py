"""
Stacked multi-layer ConvLSTM + prediction head. This is the PRIMARY M3 MVP
model.

Input:  [B, T, C_in, H, W]
Output: [B, T_out, C_out, H, W]  (matches DataContract.target_shape())

Architecture:
    Input sequence
      -> N stacked ConvLSTMCell layers (iterated over T timesteps)
      -> final hidden state of last layer, last timestep: [B, hidden_dims[-1], H, W]
      -> prediction head (1x1 conv): maps hidden channels -> T_out * C_out
      -> reshape to [B, T_out, C_out, H, W]
      -> sigmoid if target_type == "binary" (bounds output to [0,1] as a
         probability map, matching ModelOutput's documented contract)
"""

from typing import List
import torch
import torch.nn as nn

from src.models.base import BaseForecastNNModel
from src.models.convlstm_cell import ConvLSTMCell
from ml.training.strikecast_training.config import DataContract


class ConvLSTM(BaseForecastNNModel):
    model_name = "convlstm"
    model_version = "1.0.0"

    def __init__(self, contract: DataContract, hidden_dims: List[int] = None, kernel_size: int = 3):
        super().__init__(contract)
        if contract.target_type == "multiclass" and contract.num_classes is None:
            raise ValueError("target_type='multiclass' requires num_classes to be set in DataContract.")

        hidden_dims = hidden_dims or [16, 16]
        self.hidden_dims = hidden_dims
        self.num_layers = len(hidden_dims)

        cells = []
        for i in range(self.num_layers):
            in_ch = contract.input_channels if i == 0 else hidden_dims[i - 1]
            cells.append(ConvLSTMCell(in_ch, hidden_dims[i], kernel_size))
        self.cells = nn.ModuleList(cells)

        c_out = contract.num_classes if contract.target_type == "multiclass" else 1
        self._c_out = c_out
        self.head = nn.Conv2d(
            hidden_dims[-1], contract.forecast_horizon * c_out, kernel_size=1
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: [B, T, C_in, H, W] -> [B, T_out, C_out, H, W]"""
        if isinstance(x, dict):
            # Single-modality ConvLSTM used with multimodal input: fall back
            # to the first modality. Real multimodal handling is fusion.py.
            x = x[self.contract.modalities[0]]

        B, T, C, H, W = x.shape
        device, dtype = x.device, x.dtype

        layer_states = [cell.init_hidden(B, H, W, device, dtype) for cell in self.cells]

        for t in range(T):
            layer_input = x[:, t, :, :, :]  # [B, C, H, W]
            for layer_idx, cell in enumerate(self.cells):
                h_prev, c_prev = layer_states[layer_idx]
                h_next, c_next = cell(layer_input, h_prev, c_prev)
                layer_states[layer_idx] = (h_next, c_next)
                layer_input = h_next  # feeds into next layer

        final_hidden = layer_states[-1][0]  # [B, hidden_dims[-1], H, W]

        out = self.head(final_hidden)  # [B, T_out*C_out, H, W]
        T_out = self.contract.forecast_horizon
        out = out.view(B, T_out, self._c_out, H, W)

        if self.contract.target_type == "binary":
            out = torch.sigmoid(out)
        elif self.contract.target_type == "multiclass":
            # Leave as logits over the class dim — CrossEntropyLoss expects
            # raw logits, not softmax output.
            pass
        # continuous: leave as raw regression output

        return out
