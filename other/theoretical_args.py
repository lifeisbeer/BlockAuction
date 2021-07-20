from math import ceil
import sys

# num of clients as command line argument
clients = int(sys.argv[1])
matchings = int(sys.argv[2])

# gas cost parameters
deploy = 3696733
transitions =  93557 + 37869 + 31460 + 37088 + 31458 + (66868 - 51868)
register = 86869
publish1 = 95168
publish2 = 149003
del1 = 35069
del2 = 37227
commit = 51868
reveal = 170624

# block time parameters
trans = 5
tr = 288
rev = 88
cal1 = 201
cal2 = 158
reg_c = 429
reg_m = 405

# gas costs
base_cost = deploy + transitions + clients*(register+commit+reveal+del1)
min_cost = base_cost + publish2 + (matchings-1)*publish1 + (matchings+1)*(del2-del1)
max_cost = base_cost + publish2*matchings + 2*matchings*(del2-del1)

# gas costs
base_cost_rep = transitions + clients*(commit+reveal+del1)
min_cost_rep = base_cost_rep + publish2 + (matchings-1)*publish1 + (matchings+1)*(del2-del1)
max_cost_rep = base_cost_rep + publish2*matchings + 2*matchings*(del2-del1)

# runtime
base_time = 1 + trans + ceil(clients/tr) + ceil(clients/rev) + ceil((clients-matchings)/reg_c) + ceil(matchings/reg_m)
min_time = base_time + ceil(matchings/cal1)
max_time = base_time + ceil(matchings/cal2)

print("Theoretical gas cost: ({},{}]".format(min_cost, max_cost))
print("Theoretical gas cost for repeat: ({},{}]".format(min_cost_rep, max_cost_rep))
print("Theoretical runtime: ({},{}]".format(min_time, max_time))
