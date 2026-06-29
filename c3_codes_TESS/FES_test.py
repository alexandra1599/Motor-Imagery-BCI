"""
test_fes_only.py
=================
Minimal standalone script to test FES hardware — no pygame, no PsychoPy,
no EEG, no UDP. Just sends pulses on the Move channels (white/black)
exactly like a1_offline_FES.py would, so you can verify the Rehamove
and electrodes work before running the full experiment.

Usage:
    python3 test_fes_only.py
"""

import time
from a0_configFile import *
from a0_configFileSTM import *
from rehamove import *

print(f'I_STS_distMove={I_STS_distMove}, p_STS_distMove={p_STS_distMove}')
print(f'I_STS_proxMove={I_STS_proxMove}, p_STS_proxMove={p_STS_proxMove}')
print(f'I_MTS_distMove={I_MTS_distMove}, p_MTS_distMove={p_MTS_distMove}')
print(f'I_MTS_proxMove={I_MTS_proxMove}, p_MTS_proxMove={p_MTS_proxMove}')

FES = Rehamove(FES_port)

def sts_red():
    try:
        FES.pulse('red', I_STS_distMove, int(p_STS_distMove))
        print('  STS (red): OK')
    except Exception as e:
        print(f'  STS (red): FAILED - {e}')

def mts_red():
    try:
        FES.pulse('red', I_MTS_distMove, int(p_MTS_distMove))
        print('  MTS (red): OK')
    except Exception as e:
        print(f'  MTS (red): FAILED - {e}')


print('\n--- Testing STS (sensory, task period) pulses on RED ---')
print('Sending 10 pulses at FES_freq =', FES_freq, 'Hz...\n')

for i in range(10):
    print(f'Pulse {i+1}/10:')
    sts_red()
    time.sleep(1 / FES_freq)

print('\n--- Testing MTS (motor, result/reward period) pulses on RED ---')
print('Sending 10 pulses...\n')

for i in range(10):
    print(f'Pulse {i+1}/10:')
    mts_red()
    time.sleep(1 / FES_freq)

print('\nDone. If you saw "OK" for all pulses and felt/saw a muscle twitch,')
print('the FES hardware and electrodes are working correctly.')
