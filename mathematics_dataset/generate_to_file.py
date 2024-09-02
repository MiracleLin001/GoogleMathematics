# Copyright 2018 DeepMind Technologies Limited.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Example of how to write generated questions to text files.

Given an output directory, this will create the following subdirectories:

*   train-easy
*   train-medium
*   train-hard
*   interpolate
*   extrapolate

and populate each of these directories with a text file for each of the module,
where the text file contains lines alternating between the question and the
answer.

Passing --train_split=False will create a single output directory 'train' for
training data.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

# Dependency imports
from absl import app
from absl import flags
from absl import logging
from mathematics_dataset import generate
import six, json

FLAGS = flags.FLAGS

flags.DEFINE_string('output_dir', None, 'Where to write output text')
flags.DEFINE_boolean('train_split', True,
                     'Whether to split training data by difficulty')

flags.mark_flag_as_required('output_dir')


def main(save_format = 'json'):
  generate.init_modules()

  output_dir = os.path.expanduser(FLAGS.output_dir)
  if os.path.exists(output_dir):
    logging.info('output dir %s already exists', output_dir)
  logging.info('Writing to %s', output_dir)
  os.makedirs(output_dir, exist_ok=True)

  dataset_list = []
  
  for regime, flat_modules in six.iteritems(generate.filtered_modules):
    regime_dir = os.path.join(output_dir, regime)
    os.makedirs(regime_dir, exist_ok=True)
    per_module = generate.counts[regime]
    print(per_module)
    for module_name, module in six.iteritems(flat_modules):
      print(module_name)
      if save_format == 'json':
        path = os.path.join(regime_dir, module_name + '.json')
        for k in range(per_module):
          problem, _ = generate.sample_from_module(module)
          dataset_list.append(
            {
              'question': str(problem.question),
              'answer': str(problem.answer)
            }
          )
        with open(path, 'w', encoding= 'utf-8') as text_file:
          json.dump(dataset_list, text_file, indent=4, )
      elif save_format == 'jsonl':
        path = os.path.join(regime_dir, module_name + '.jsonl')
        with open(path, 'w', encoding= 'utf-8') as text_file:
          for _ in range(per_module):
            problem, _ = generate.sample_from_module(module)
            dataset_dict.update(
              {
                'question': str(problem.question),
                'answer': str(problem.answer)
              }
            )
            json.dump(dataset_dict, text_file)
            text_file.write('\n')
      elif save_format == 'txt':
        path = os.path.join(regime_dir, module_name + '.txt')
        with open(path, 'w') as text_file:
          for _ in range(per_module):
            problem, _ = generate.sample_from_module(module)
            text_file.write(str(problem.question) + '\n')
            text_file.write(str(problem.answer) + '\n')
      else:
        raise ValueError(f'Unknown save format: {save_format}')
      print(f'Wrote {path} with {per_module} examples')
      


if __name__ == '__main__':
  import sys
  FLAGS(sys.argv)
  main()
