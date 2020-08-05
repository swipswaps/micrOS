#!/usr/bin/env python3

import os
import sys
import atexit
from random import randint
MYPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(MYPATH, '../tools'))
import socketClient

DEVICE = 'ImpiGame'
BASE_CMD = ['--dev', DEVICE]
CMD_PIPE_SEP = '<a>'
SERVO_CENTER_VAL = 77


def app(iteration=30):
    global DEVICE, BASE_CMD, CMD_PIPE_SEP
    for _ in range(iteration):
        piped_commands = []

        args = BASE_CMD + ['servo', 'Servo({})'.format(SERVO_CENTER_VAL)]
        print("CMD: {}".format(args))
        args.append(CMD_PIPE_SEP)
        piped_commands += args

        for _ in range(randint(1, 6)):
            duty = randint(55, 100)
            args = ['servo', 'Servo({duty})'.format(duty=duty)]
            print("\tCMD: {}".format(args))
            args.append(CMD_PIPE_SEP)
            piped_commands += args

        args += ['servo', 'Servo({})'.format(SERVO_CENTER_VAL)]
        print("CMD: {}".format(args))
        piped_commands += args

        print("CMD PIPE: {}".format(piped_commands))
        socketClient.run(piped_commands)

    deinit_servo()


def deinit_servo():
    args = [BASE_CMD, ['servo', 'Servo({})'.format(SERVO_CENTER_VAL)], ['servo', 'Servo_deinit']]
    print("DEINIT SERVO, SET TO {} and DEINIT".format(SERVO_CENTER_VAL))
    socketClient.run(args)


atexit.register(deinit_servo)

if __name__ == "__main__":
    app()
