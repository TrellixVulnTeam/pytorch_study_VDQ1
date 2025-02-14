# -*- coding: utf-8 -*-
import torch
import torch.nn as nn
from torch.autograd import Variable
from torch import optim
import torch.nn.functional as F

from datatools import MAX_LENGTH
from datatools import USE_CUDA


class EncoderRNN(nn.Module):
    def __init__(self, input_size, hidden_size):
        """
        :param input_size: word vocab size
        :param hidden_size: 词向量的维度、RNN的hidden_size (设置为一样是为什么？)
        """
        super(EncoderRNN, self).__init__()
        self.hidden_size = hidden_size

        self.embedding = nn.Embedding(input_size, hidden_size)
        self.gru = nn.GRU(input_size=hidden_size, hidden_size=hidden_size)

    def forward(self, input, hidden):
        """
        :param input: a word of the input sentence, Variable, size[1]
        :param hidden: 初始hidden, variable, [1, 1, hidden_size]
        :return:
           'hidden': Variable, [1, 1, hidden_size]
           'output': Variable, [1, 1, hidden_size]
        """
        embedded = self.embedding(input).view(1, 1, -1)  # ??
        output = embedded
        # 得到output和t时刻的hidden
        output, hidden = self.gru(output, hidden)
        return output, hidden

    def initHidden(self):
        """init RNN hidden state"""
        result = Variable(torch.zeros(1, 1, self.hidden_size))
        if USE_CUDA:
            return result.cuda()
        else:
            return result


class DecoderRNN(nn.Module):
    def __init__(self, hidden_size, output_size):
        """
        :param hidden_size:词向量的维度、RNN的hidden_size
        :param output_size: word vocab size
        """
        super(DecoderRNN, self).__init__()
        self.hidden_size = hidden_size

        self.embedding = nn.Embedding(output_size, hidden_size)
        self.gru = nn.GRU(input_size=hidden_size, hidden_size=hidden_size)
        self.out = nn.Linear(hidden_size, output_size)
        self.softmax = nn.LogSoftmax()

    def forward(self, input, hidden, encoder_outputs=None):
        """
        :param input: the SOS token
        :param hidden: the context vector, from Encoder
        :param encoder_outputs: 为了使用调用方法相同设置的参数, 此处为null
        :return:
         'output', tensor [1, output_size], output vocab probability distribution
         'hidden': decoder每一时刻的hidden state
         'None': 为了和AttentionDecoder兼容设置的参数
        """
        output = self.embedding(input).view(1, 1, -1)
        output = F.relu(output)  # 这一层怎么理解？
        output, hidden = self.gru(output, hidden)
        # output[1, hidden_size] -> [1, output_size]
        output = self.softmax(self.out(output[0]))
        return output, hidden, None

    def initHidden(self):
        """init RNN hidden state(we don't use it)"""
        result = Variable(torch.zeros(1, 1, self.hidden_size))
        if USE_CUDA:
            return result.cuda()
        else:
            return result


class AttnDecoderRNN(nn.Module):
    def __init__(self, hidden_size, output_size, dropout_p=0.1,
                 max_length=MAX_LENGTH):
        """
        :param hidden_size: 词向量的维度、RNN的hidden_size
        :param output_size: 目标sequence vocab size
        :param dropout_p: dropout rate
        :param max_length: 输入句子的最大长度
        """
        super(AttnDecoderRNN, self).__init__()
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.dropout_p = dropout_p
        self.max_length = max_length

        self.embedding = nn.Embedding(output_size, hidden_size)

        # use feed-forward layer to calculating the attention
        self.attn = nn.Linear(self.hidden_size * 2, self.max_length)
        self.attn_combine = nn.Linear(self.hidden_size * 2, self.hidden_size)

        self.dropout = nn.Dropout(self.dropout_p)
        self.gru = nn.GRU(self.hidden_size, self.hidden_size)

        self.out = nn.Linear(self.hidden_size, self.output_size)

    def forward(self, input, hidden, encoder_outputs):
        """
        :param input: the target input word, [1 x 1]
        :param hidden: [1 x 1 x hidden_size]
        :param encoder_outputs: variable. [max_length, hidden_size],
           the every time output of encoder, use to calc attention
        :return:
         'output':, variable, [1 x output_size], the output probability
            distribution
         'attn_weights', variable,  [1 x max_length], a probability
              distribution
        """
        embedded = self.embedding(input).view(1, 1, -1)
        embedded = self.dropout(embedded)

        # (此处的attention机制怎么理解？)
        # use the decoder's input and hidden state as the feed-forward inputs
        attn_weights = F.softmax(self.attn(torch.cat((embedded[0], hidden[0]), 1)))
        # calc the weight sum
        attn_applied = torch.bmm(attn_weights.unsqueeze(0),
                                 encoder_outputs.unsqueeze(0))
        # combine input(??)
        output = torch.cat((embedded[0], attn_applied[0]), 1)
        output = self.attn_combine(output).unsqueeze(0)

        output = F.relu(output)
        output, hidden = self.gru(output, hidden)
        # tensor output[1 x output_size]
        output = F.log_softmax(self.out(output[0]))
        return output, hidden, attn_weights

    def initHidden(self):
        """init the hidden state"""
        result = Variable(torch.zeros(1, 1, self.hidden_size))
        if USE_CUDA:
            return result.cuda()
        else:
            return result




