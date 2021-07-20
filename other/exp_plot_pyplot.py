import numpy as np
import matplotlib.pyplot as plt

clients = np.array([10,100,1000])
gas = np.array([7887035, 44917739, 438954083])
c1 = "tab:blue"
blocks = np.array([25, 168, 1818])
c2 = "tab:orange"

# create figure and axis objects with subplots()
fig,ax = plt.subplots()
# make a plot
ax.plot(clients, gas, color=c1, linewidth=4, marker="o", markersize=10, label='gas cost')
# set x-axis label
ax.set_xlabel("Number of Clients", fontsize=14)
# set y-axis label
ax.set_ylabel("Gas Cost", color=c1, fontsize=14)

# twin object for two different y-axis on the sample plot
ax2=ax.twinx()
# make a plot with different y-axis using second axis object
ax2.plot(clients, blocks, color=c2, linewidth=4, linestyle=':', markersize=8, markeredgewidth=2, marker='x', label='duration')
ax2.set_ylabel("Duration (in blocks)", color=c2, fontsize=14)

ax.legend()
ax2.legend(loc='upper left', bbox_to_anchor=(0., 0., 0., 0.9))

plt.show()


'''
m1, b1 = np.polyfit(clients, gas, 1)
plt.plot(clients, gas, 'o')
plt.plot(clients, m1*clients + b1)
plt.show()

m2, b2 = np.polyfit(clients, blocks, 1)
plt.plot(clients, blocks, 'o')
plt.plot(clients, m2*clients + b2)
plt.show()
'''
