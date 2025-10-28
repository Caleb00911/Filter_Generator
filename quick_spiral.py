#!/usr/bin/env python3
import itertools
import sys
import textwrap

import numpy as np



class Operation:
    def __init__(self):
        pass
    def to_code(self,env):
        sys.exit("Not implemented.")
    def to_numpy(self):
        sys.exit("Not implemented.")
    def __repr__(self):
        return self.__str__()
        

class DFT(Operation):
    def  __init__(self,n):
        self.n=n
        self.size=(n,n)
    def __str__(self):
        return "DFT({n})".format(n=self.n)

class FMADD(Operation):
    def __init__(self,scale):
        self.scale=scale
        self.size=(1,1)
    def to_code(self,env):
        code="""
({y}) += ({x}) * ({a});       
""".format(x=env['x'],y=env['y'],a=self.scale)
        return textwrap.indent(code,f"{'    '*env['indent']}")
        
class Mat(Operation):
    def __init__(self,mat,mat_format='dense'):
        self.mat = np.asmatrix(mat)
        self.size = self.mat.shape
    def to_code(self,env):
        code=""
        fmadd=env['fmadd']
        scale=env['scale']
#        for i in range(0,self.mat.shape[0]):
#            for j in range(self.mat.shape[1]):
#                #code+="y[{i}]+= ({scale}) * x[{j}] * {a};\n".format(i=i,j=j,scale=scale,a=self.mat[(i,j)])
#                env2=dict(env)
#                code+=fmadd(self.mat[(i,j)]).to_code(env)
#        return code
        io="io_{cur}".format(cur=env['cur']) # TODO: I need a way to generate fresh variable names
        jo="jo_{cur}".format(cur=env['cur']) # TODO: I need a way to generate fresh variable names
        env['cur']+=1
        env2=dict(env)
        #env2['fmadd']=fmadd.child?


# HERE: Mat is really MatVec and that's a problem.
# TODO: io,jo need to stride base on the size of the fmadd
# really what needs to happen is that we have blocked and unblocked matvec.
# The blocked case the problems in terms of smaller blocked/unblocked.
#
# Rewrite as MatVec(alpha,beta,A)
# When size=(1,1) then we do the actually math
# Otherwise it's a sub problem.

# TODO: The size should be scaled by the FMADD inside
#       Same goes as the indices.

# ({y})[{io}]+= ({x})[{jo}] * A[{io},{jo}];    
        code ="""
for(int {io} = 0; {io} < {io_size}; io++)
    for(int {jo} = 0; {jo} < {jo_size}; jo++)
    {{
        {A}
    }}
""".format(x=env['x'],y=env['y'],
           io=io,io_size=self.size[0],
           jo=jo, jo_size=self.size[1],
           A=fmadd("A[{io},{jo}]").to_code(env))
        return textwrap.indent(code,f"{'    '*env['indent']}")
            
        
        
class F(Operation):
    def  __init__(self,n):
        self.n=n
        self.size=(n,n)
    def __str__(self):
        return "F({n})".format(n=self.n)
    def to_code(self,env):
        if self.n == 2:
            code="""{{
({y})[0]=({x})[0]+({x})[1];
({y})[1]=({x})[0]-({x})[1];
}}
""".format(x=env['x'],y=env['y'])
            return textwrap.indent(code,f"{'    '*env['indent']}")


# high order operators
class HighOrderOperation(Operation):
    pass

class I_Tensor_A(HighOrderOperation):
    def __init__(self,n,A):
        self.n     = n
        self.child = A
        self.size  =(n*A.size[0],n*A.size[1])
    def __str__(self):
        return "I_Tensor_A({n},{a})".format(n=self.n,a=self.child)
    def to_code(self,env):
        io="io_{cur}".format(cur=env['cur']) # TODO: I need a way to generate fresh variable names
        env['cur']+=1
        enva=dict(env)
        enva['x']="(&({base})[{io}*{io_step}])".format(base=enva['x'],io=io,io_step=self.child.size[1])
        enva['y']="(&({base})[{io}*{io_step}])".format(base=enva['y'],io=io,io_step=self.child.size[0])
        code ="""
for(int {io} = 0; {io} < {io_size}; io++)
{{
{A}
}}
""".format(io=io,io_size=self.n,A=self.child.to_code(enva))
        return textwrap.indent(code,f"{'    '*env['indent']}")
        
class A_Tensor_I(HighOrderOperation):
    def __init__(self,n,A):
        self.n     = n
        self.child = A
        self.size  =(n*A.size[0],n*A.size[1])
    def __str__(self):
        return "A_Tensor_I({n},{a})".format(n=self.n,a=self.child)

class Compose(HighOrderOperation):
    def __init__(self,A,B):
        self.A=A
        self.B=B
    def __str__(self):
        return "Compose({A},{B})".format(A=self.A,B=self.B)
    def to_code(self,env):
        enva=dict(env)
        envb=dict(env)
        enva['y']='tmp'
        envb['x']='tmp'
        code ="""
{{
float tmp[{size}];
{A}
{B}
}}
        """.format(size=self.A.size[1],A=self.A.to_code(enva),B=self.B.to_code(envb))
        return textwrap.indent(code,f"{'    '*env['indent']}")
        



class Replace:
    def __init__(self,operation,algo_list):
        self.operation=operation
        self.algo_list=algo_list
    def __str__(self):
        return "Replace({op},{algo_list})".format(op=self.operation,algo_list=self.algo_list)

# lhs(d) || rhs (p \in P) || condition:D -->{T,F} | parameter_space:  D --> \Power{P}, d|-->P 


# I have some left hand side with parameter d
# I have a potential right hand side parameterized by p \in P
# I have a condition that maps d to true or false to say if the rhs will apply
# I have a parameter_space that takes a d \in D and produces a set of parameters P

def apply_rule_DFT(n):
    # apply a rule for Cooley-Tukey
    if n >= 4:
        # generate a space of parameters that is valid for our rhs given our lhs
        param_space = itertools.filterfalse(lambda x: x[0]*x[1]!=n, itertools.product(range(n),range(n)))
        #algo_space  = ["Algorithm_DFTCT(DFT({m}), DFT({k}))".format(m=apply_rule_DFT(p[0]),
        #                                                             k=apply_rule_DFT(p[1])) for p in param_space]

        
        algo_space  = [Compose(I_Tensor_A(p[0],DFT(p[1])), A_Tensor_I(p[1],DFT(p[0]))) for p in param_space] # <<--- this was the good one. RMV
        #algo_space  = [Compose(I_Tensor_A(p[0],apply_rule_DFT(p[1])), A_Tensor_I(p[1],apply_rule_DFT(p[0]))) for p in param_space]

        
        #return "Replace(DFT({n}),{algs})".format(algs=algo_space, n=n)
        return Replace(DFT(n),algo_space)
        
        
#        ll = []
#        for p in param_space:
            #print()
#            ll.append("Replace(DFT({n}), Algorithm_DFTCT(DFT({m}), DFT({k})))".format(n=n,m=apply_rule_DFT(p[0]),k=p[1]))

#        return ll
        
    # apply rule for base case
    if n == 2:
        #return "Replace(DFT{n},[F2()])".format(n=n)
        return Replace(DFT(n),[F(2)])


def apply_rule_DFT_easy(n):
    # apply a rule for Cooley-Tukey
    if n >= 4:
        # generate a space of parameters that is valid for our rhs given our lhs
        param_space = itertools.filterfalse(lambda x: x[0]*x[1]!=n, itertools.product(range(n),range(n)))        
        algo_space  = ["Algorithm_DFTCT(DFT({m}), DFT({k}))".format(m=apply_rule_DFT(p[0]),
                                                                    k=apply_rule_DFT(p[1])) for p in param_space]
        
        return "Replace(DFT({n}),{algs})".format(algs=algo_space, n=n)
        
    # apply rule for base case
    if n == 2:
        return "Replace(DFT{n},[F2()])".format(n=n)

    


    
#print([F(2)])
print(apply_rule_DFT_easy(2))
print(apply_rule_DFT_easy(8))
print(apply_rule_DFT_easy(32))

env = {'x':'x','y':'y','scale':1, 'fmadd':FMADD,'indent':0, 'cur':0}

#print(F(2).to_code(env))

#print(Compose(F(2),F(2)).to_code(env))
#print(I_Tensor_A(4,F(2)).to_code(env))
#print("=========")
#print(Mat('1 2; 3 4').to_code(env))

#print(FMADD(5).to_code(env))
#print(I_Tensor_A(4,FMADD(5)).to_code(env)) # TODO: Lambda this into the env fmadd(a) --> I_Tensor_A(4,FMADD(a)
#
# lhs <---> Operation
# rhs <---> Algorithm(operations...operation)
# Code(Algorithm) <---> Implementation

#Replace(lhs,[rhs])

#Algorithm_DFTCT()


i4_tensor_fmadd = lambda a: I_Tensor_A(4,FMADD(a))
env2 = dict(env)
env2['fmadd'] = i4_tensor_fmadd

print(i4_tensor_fmadd(4).size)
print(Mat('1 2; 3 4').to_code(env2))



#Tensor(Mat('1 2; 3 4'),Mat('5 6; 7 8'))
#print(Mat('1 2; 3 4').to_code(env))



Replace(DFT(8),['Algorithm_DFTCT(DFT(Replace(DFT(2),[F(2)])), DFT(Replace(DFT(4),[Compose(I_Tensor_A(2,DFT(2)),A_Tensor_I(2,DFT(2)))])))', 'Algorithm_DFTCT(DFT(Replace(DFT(4),[Compose(I_Tensor_A(2,DFT(2)),A_Tensor_I(2,DFT(2)))])), DFT(Replace(DFT(2),[F(2)])))'])

