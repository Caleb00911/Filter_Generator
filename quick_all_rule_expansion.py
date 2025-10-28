#!/usr/bin/env python3
import itertools
import sys
import textwrap

import numpy as np


class Circuit:
    def __init__(self,node_set):
        self.node_set=node_set
    def to_spice(self):
        pass


class Filt:
    def __init__(self,r,c,l,in0,in1,out0,out1):
        self.r = r
        self.c = c
        self.l = l
        self.in0 = in0
        self.in1 = in1
        self.out0 = out0
        self.out1 = out1
    def __str__(self):
        return f"Filt({self.in0},{self.in1},{self.out0},{self.out1})"


class Compose:
    def __init__(self):
        pass

        
def build_all_circuits():
    pass


# playing around with sets of nodes
node_set_0 = set(["g","vin","s"])
print([(i0,i1) for (i0,i1) in itertools.combinations(node_set_0,2)])

node_cnt=0
n_a=f"n_{node_cnt}"
node_cnt+=1
n_b=f"n_{node_cnt+1}"
node_cnt+=1

node_set_1 = node_set_0.union(set([n_a,n_b]))

print([(i0,i1) for (i0,i1) in itertools.combinations(node_set_1,2)])

print([Filt(1,1,1,i0,i1,n_a,n_b) for (i0,i1) in itertools.combinations(node_set_1,2)])






