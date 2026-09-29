from __future__ import annotations
import torch
from torch import nn
class ConvLSTMCell(nn.Module):
    def __init__(self,input_dim,hidden_dim,kernel_size=3):
        super().__init__(); self.hidden_dim=hidden_dim
        self.conv=nn.Conv2d(input_dim+hidden_dim,4*hidden_dim,kernel_size,padding=kernel_size//2)
    def forward(self,x,state):
        h,c=state; i,f,o,g=torch.chunk(self.conv(torch.cat([x,h],dim=1)),4,dim=1)
        i=torch.sigmoid(i); f=torch.sigmoid(f); o=torch.sigmoid(o); g=torch.tanh(g)
        c=f*c+i*g; h=o*torch.tanh(c); return h,c
class ConvLSTMClassifier(nn.Module):
    def __init__(self,input_dim=8,hidden_dim=12):
        super().__init__(); self.hidden_dim=hidden_dim; self.cell=ConvLSTMCell(input_dim,hidden_dim)
        self.head=nn.Sequential(nn.AdaptiveAvgPool2d(1),nn.Flatten(),nn.Linear(hidden_dim,1))
    def forward(self,x):
        b,t,c,h,w=x.shape; h0=torch.zeros(b,self.hidden_dim,h,w,device=x.device); c0=torch.zeros_like(h0)
        state=(h0,c0)
        for k in range(t): state=self.cell(x[:,k],state)
        return self.head(state[0]).squeeze(1)
