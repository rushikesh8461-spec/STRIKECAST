"""
Single ConvLSTM cell (Shi et al., 2015 convention): replaces the fully-
connected gates of a standard LSTM with 2D convolutions, so hidden/cell
state retain spatial structure instead of being flattened.
"""

import torch
import torch.nn as nn


class ConvLSTMCell(nn.Module):
    def __init__(self, input_channels: int, hidden_channels: int, kernel_size: int = 3):
        super().__init__()
        padding = kernel_size // 2  # "same" padding, keeps H,W constant

        self.input_channels = input_channels
        self.hidden_channels = hidden_channels

        # Single conv producing all 4 gates at once (input, forget, output, cell)
        self.conv = nn.Conv2d(
            in_channels=input_channels + hidden_channels,
            out_channels=4 * hidden_channels,
            kernel_size=kernel_size,
            padding=padding,
            bias=True,
        )

    def forward(self, x: torch.Tensor, h_prev: torch.Tensor, c_prev: torch.Tensor):
        """
        x:      [B, C_in, H, W]
        h_prev: [B, C_hidden, H, W]
        c_prev: [B, C_hidden, H, W]
        returns (h_next, c_next), each [B, C_hidden, H, W]
        """
        combined = torch.cat([x, h_prev], dim=1)  # [B, C_in+C_hidden, H, W]
        gates = self.conv(combined)  # [B, 4*C_hidden, H, W]

        i_gate, f_gate, o_gate, g_gate = torch.chunk(gates, 4, dim=1)
        i_gate = torch.sigmoid(i_gate)
        f_gate = torch.sigmoid(f_gate)
        o_gate = torch.sigmoid(o_gate)
        g_gate = torch.tanh(g_gate)

        c_next = f_gate * c_prev + i_gate * g_gate
        h_next = o_gate * torch.tanh(c_next)

        return h_next, c_next

    def init_hidden(self, batch_size: int, height: int, width: int, device, dtype):
        h = torch.zeros(batch_size, self.hidden_channels, height, width, device=device, dtype=dtype)
        c = torch.zeros(batch_size, self.hidden_channels, height, width, device=device, dtype=dtype)
        return h, c
