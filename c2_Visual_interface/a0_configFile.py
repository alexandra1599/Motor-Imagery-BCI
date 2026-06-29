import random
import numpy as np 
from itertools import repeat 
# TIMING CONSTANTS:
# *****************

updateRate= 0.95


ExperimentConfigureTime= 2
fixationCrossTime= 1
cueTime= 1.5
timeout= 7
taskTime= 5
resultTime= 2
restTime= 	1.5
fixationTime = 2
# trials = [-1,1,1,-1,-1,1];
detectionThresholdRest = 0.7 #0.5
detectionThresholdMove = 0.70 #0.5      
  
detectionThresholdRest = 0.7 # rest
detectionThresholdMove = 0.7 # move


n_Rest=5 #Should be 10
n_Move=5  #Should be 10


# Randomize the order of trials:
Move_array = list(repeat(1, n_Move))
Rest_array = list(repeat(0, n_Rest))
total = len(Move_array) + len(Rest_array)
trials = np.zeros(total)
all_arrays = Move_array + Rest_array

for i in range(0, total, 1):
    trials[i] = random.sample(all_arrays, 1)[0]
    all_arrays.remove(trials[i])

trials = np.append([1,0],trials)

#trials=np.concatenate((np.asarray(np.ones((n_flexion))),-1*np.asarray(np.ones(n_extension))),axis=0)
#np.random.shuffle(trials)

#  NOTES:
# ********
# Class (+1): extension (right)
# Class (-1): flexion (left)
