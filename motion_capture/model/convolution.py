import torch as T
import torch.nn as nn


class ConvBlock(nn.Module):
    def __init__(
        self,
        in_channels: int, 
        out_channels: int,
        kernel_size: int,
        stride: int = 1,
        bias: bool = False,
        dilation: int = 1,
        padding: int = 0,
        groups: int = 1):
            
        super(type(self), self).__init__()
        
        self.conv = nn.Conv2d(
            in_channels=in_channels, out_channels=out_channels,
            kernel_size=kernel_size, stride=stride, padding=padding, dilation=dilation, 
            groups=groups, bias=bias, padding_mode = "zeros")
        self.bn = nn.BatchNorm2d(out_channels)
        self.act = nn.SiLU()
    
    def forward(self, x: T.Tensor):
        return self.act(self.bn(self.conv(x)))


class BottleneckBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, shortcut: bool = True):
        super(type(self), self).__init__()
        
        self.conv1 = ConvBlock(in_channels, (in_channels + out_channels) // 2, kernel_size, padding=1)
        self.conv2 = ConvBlock((in_channels + out_channels) // 2, out_channels, kernel_size, padding=1)
        self.add = shortcut and in_channels == out_channels
        
    def forward(self, x):
        return x + self.conv2(self.conv1(x)) if self.add else self.conv2(self.conv1(x))


class C2f(nn.Module):
    # CSP Bottleneck with 2 convolutions
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, n: int = 1, shortcut: bool = True):
        super(type(self), self).__init__()
        
        self.hidden_channels = (in_channels + out_channels) // 2
        
        self.conv1 = ConvBlock(in_channels, self.hidden_channels * 2, kernel_size=kernel_size, stride=1)
        
        self.module_list = nn.ModuleList(BottleneckBlock(
            in_channels=self.hidden_channels, 
            out_channels=self.hidden_channels, 
            kernel_size=3, 
            shortcut=shortcut) for _ in range(n))
        
        self.conv2 = ConvBlock((2 + n) * self.hidden_channels, out_channels, kernel_size=kernel_size, stride=1)
        
    def forward(self, x):
        y = list(self.conv1(x).split((self.hidden_channels, self.hidden_channels), 1))
        y.extend(module(y[-1]) for module in self.module_list)
        return self.conv2(T.cat(y, dim = 1))

class SPPF(nn.Module):
    # Spatial Pyramid Pooling - Fast (SPPF) layer for YOLOv5 by Glenn Jocher
    def __init__(self, in_channels: int, out_channels: int, maxpool_kernel_size=5): # equivalent to SPP(k=(5, 9, 13))
        super(type(self), self).__init__()
        
        self.conv1 = ConvBlock(in_channels, in_channels, kernel_size=1, stride=1)
        self.conv2 = ConvBlock(in_channels * 4, out_channels, kernel_size=1, stride=1)
        self.max_pool = nn.MaxPool2d(kernel_size=maxpool_kernel_size, stride=1, padding=maxpool_kernel_size//2)

    def forward(self, x):
        x = self.conv1(x)
        x1 = self.max_pool(x)
        x2 = self.max_pool(x1)
        x3 = self.max_pool(x2)
        return self.conv2(T.cat([x, x1, x2, x3], 1))

class Detection(nn.Module):
    # based on YOLOv8 head
    def __init__(self, in_channels: int, out_length: int, num_classes: int):
        super(type(self), self).__init__()
        
        self.out_length = out_length
        self.num_classes = num_classes
        
        self.bbox = nn.Sequential(
            ConvBlock(in_channels, in_channels, kernel_size=3, stride=1, padding=1),
            ConvBlock(in_channels, in_channels, kernel_size=1, stride=1, padding=1),
            nn.Conv2d(in_channels, 4 * out_length, kernel_size=1, stride=1, padding=0)
        )
        self.class_ = nn.Sequential(
            ConvBlock(in_channels, in_channels, kernel_size=3, stride=1, padding=1),
            ConvBlock(in_channels, in_channels, kernel_size=1, stride=1, padding=1),
            nn.Conv2d(in_channels, num_classes * out_length, kernel_size=1, stride=1, padding=0)
        )
        
    def forward(self, x):
        bbox = self.bbox(x).permute(0, 2, 3, 1)
        class_ = self.class_(x).permute(0, 2, 3, 1)
        return bbox, class_
