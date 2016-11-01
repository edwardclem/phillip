import os
import time
import RL
import util
from default import *
import numpy as np
from collections import defaultdict
from gc import get_objects

# some helpers for debugging memory leaks

def count_objects():
  counts = defaultdict(int)
  for obj in get_objects():
    counts[type(obj)] += 1
  return counts

def diff_objects(after, before):
  diff = {k: after[k] - before[k] for k in after}
  return {k: i for k, i in diff.items() if i}

class Trainer(Default):
  _options = [
    #Option("debug", action="store_true", help="set debug breakpoint"),
    #Option("-q", "--quiet", action="store_true", help="don't print status messages to stdout"),
    Option("init", action="store_true", help="initialize variables"),

    Option("sweeps", type=int, default=1, help="number of sweeps between saves"),
    Option("batches", type=int, default=1, help="number of batches per sweep"),
    Option("batch_size", type=int, default=1, help="number of trajectories per batch"),
    Option("batch_steps", type=int, default=1, help="number of gradient steps to take on each batch"),

    Option("dump", type=str, default="127.0.0.1", help="interface to listen on for experience dumps"),

    Option("params", type=str, help="path to a json file from which to load params"),
  ]
  
  _members = [
    ("model", RL.Model),
  ]
  
  def __init__(self, params=None, **kwargs):
    if params is None:
      args = {}
    else:
      import json
      with open(params, 'r') as f:
        args = json.load(f)['train']
    
    util.update(args, mode=RL.Mode.TRAIN, **kwargs)
    print(args)
    Default.__init__(self, **args)
    
    if self.init:
      self.model.init()
      self.model.save()
    else:
      self.model.restore()
  
  def train(self):
    import zmq

    context = zmq.Context()

    socket = context.socket(zmq.PULL)
    sock_addr = "tcp://%s:%d" % (self.dump, util.port(self.model.name))
    print("Binding to " + sock_addr)
    socket.bind(sock_addr)

    sweep_size = self.batches * self.batch_size
    print("Sweep size", sweep_size)

    sweeps = 0

    before = count_objects()

    while True:
      start_time = time.time()
      
      experiences = []
      
      for _ in range(sweep_size):
        experiences.append(socket.recv_pyobj())
      
      collect_time = time.time()
      
      for _ in range(self.sweeps):
        from random import shuffle
        shuffle(experiences)
        
        for batch in util.chunk(experiences, self.batch_size):
          self.model.train(batch, self.batch_steps)
      
      train_time = time.time()
      
      self.model.save()
      
      save_time = time.time()
      
      sweeps += 1
      
      if False:
        after = count_objects()
        print(diff_objects(after, before))
        before = after
      
      save_time -= train_time
      train_time -= collect_time
      collect_time -= start_time
      
      print(sweeps, sweep_size, collect_time, train_time, save_time)

if __name__ == '__main__':
  from argparse import ArgumentParser
  parser = ArgumentParser()

  for opt in Trainer.full_opts():
    opt.update_parser(parser)

  for model in RL.models.values():
    for opt in model.full_opts():
      opt.update_parser(parser)

  args = parser.parse_args()
  trainer = Trainer(**args.__dict__)
  trainer.train()

