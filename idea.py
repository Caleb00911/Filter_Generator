
def apply_rule_DFT(n):
    # apply a rule for Cooley-Tukey
    if n >= 4:
        # generate a space of parameters that is valid for our rhs given our lhs
        param_space = itertools.filterfalse(lambda x: x[0]*x[1]!=n, itertools.product(range(n),range(n)))
        algo_space  = [Compose(I_Tensor_A(p[0],DFT(p[1])), A_Tensor_I(p[1],DFT(p[0]))) for p in param_space]

        return Replace(DFT(n),algo_space)
                
    # apply rule for base case
    if n == 2:
        #return "Replace(DFT{n},[F2()])".format(n=n)
        return Replace(DFT(n),[F(2)])
