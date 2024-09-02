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

"""Algebra-related questions, e.g., "Solve 1 + x = 2."."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import functools
import random

# Dependency imports
from mathematics_dataset import example
from mathematics_dataset.sample import linear_system
from mathematics_dataset.sample import number
from mathematics_dataset.sample import ops
from mathematics_dataset.sample import polynomials
from mathematics_dataset.util import composition
from mathematics_dataset.util import display
import numpy as np

import sympy


_ENTROPY_TRAIN = (3, 10)
_ENTROPY_INTERPOLATE = (8, 8)
_ENTROPY_EXTRAPOLATE = (12, 12)

# In generating a polynomial with real roots (where the roots are generated
# sequentially), this is the probability of taking a previous root, thus giving
# at least one repeated root, rather than sampling a new number. The value is
# somewhat arbitrary, but gives a "medium probability" of seeing a repeated root
# for lowish degree polynomials.
_POLY_PROBABILITY_REPEATED_ROOT = 0.2


def _make_modules(entropy):
  """Returns modules given "difficulty" parameters."""
  sample_args_pure = composition.PreSampleArgs(1, 1, *entropy)
  sample_args_composed = composition.PreSampleArgs(2, 4, *entropy)

  return {
      # Solving equations:
      'polynomial_roots': functools.partial(
          polynomial_roots, None, sample_args_pure),
      'polynomial_roots_composed': functools.partial(
          polynomial_roots, None, sample_args_composed),
      'linear_1d': functools.partial(
          solve_linear_1d, None, sample_args_pure),
      'linear_1d_composed': functools.partial(
          solve_linear_1d, None, sample_args_composed),
      'linear_2d': functools.partial(
          solve_linear_2d, None, sample_args_pure),
      'linear_2d_composed': functools.partial(
          solve_linear_2d, None, sample_args_composed),

      # Sequences:
      'sequence_next_term': functools.partial(sequence_next_term, *entropy),
      'sequence_nth_term': functools.partial(sequence_nth_term, *entropy),
  }


def train(entropy_fn):
  """Returns dict of training modules."""
  return _make_modules(entropy_fn(_ENTROPY_TRAIN))


def test():
  """Returns dict of testing modules."""
  return _make_modules(_ENTROPY_INTERPOLATE)


def test_extra():
  """Returns dict of extrapolation testing modules."""
  sample_args_pure = composition.PreSampleArgs(1, 1, *_ENTROPY_EXTRAPOLATE)
  return {
      'polynomial_roots_big': functools.partial(
          polynomial_roots, None, sample_args_pure),
  }


def _sample_roots(entropy):
  """Generates `num_distinct + num_repeated` polynomial roots."""
  num_roots = random.randint(2, 5)

  num_repeated = np.random.binomial(
      num_roots - 1, _POLY_PROBABILITY_REPEATED_ROOT)
  # Slight hack: don't allow all the roots to be repeated when the entropy is
  # high, as this can create very large coefficients.
  if entropy > 4:
    num_repeated = min(num_repeated, int(num_roots / 2))

  num_distinct = num_roots - num_repeated

  entropies = entropy * np.random.dirichlet(np.ones(num_distinct))

  roots = []

  for root_entropy in entropies:
    # Generates a root with small probability of being rational.
    # (Otherwise when we multiply out the denominators, we get really large
    # coefficients in our polynomial.)
    if random.random() < 0.1:
      root = number.non_integer_rational(root_entropy, True)
    else:
      root = number.integer(root_entropy, True)
    roots.append(root)

  for _ in range(num_repeated):
    roots.append(random.choice(roots[:num_distinct]))

  return roots


def _polynomial_coeffs_with_roots(roots, scale_entropy):
  """Returns a polynomial with the given roots.

  The polynomial is generated by expanding product_{root in roots} (x - root),
  and then (1) scaling by the coefficients so they are all integers with lcm 1,
  and then (2) further scaling the coefficients by a random integer or rational
  with `scale_entropy` digits.

  Args:
    roots: List of values.
    scale_entropy: Float; entropy of the random coefficient scaling.

  Returns:
    List of coefficients `coeffs`, such that `coeffs[i]` is the coefficient of
    variable ** i.
  """
  variable = sympy.Symbol('x')  # doesn't matter, only use coefficients
  polynomial = sympy.Poly(sympy.prod([variable - root for root in roots]))
  coeffs_reversed = polynomial.all_coeffs()
  assert len(coeffs_reversed) == len(roots) + 1
  coeffs = list(reversed(coeffs_reversed))
  # Multiply terms to change rationals to integers, and then maybe reintroduce.
  lcm = sympy.lcm([sympy.denom(coeff) for coeff in coeffs])
  if scale_entropy > 0:
    while True:
      scale = number.integer_or_rational(scale_entropy, signed=True)
      if scale != 0:
        break
  else:
    scale = 1
  return [coeff * scale * lcm for coeff in coeffs]


def polynomial_roots(value, sample_args, context=None):
  """E.g., "Solve 2*x**2 - 18 = 0."."""
  del value  # not currently used
  # is_question = context is None
  if context is None:
    context = composition.Context()

  entropy, sample_args = sample_args.peel()
  scale_entropy = min(entropy / 2, 1)

  roots = _sample_roots(entropy - scale_entropy)
  solutions = sorted(list(sympy.FiniteSet(*roots)))
  coeffs = _polynomial_coeffs_with_roots(roots, scale_entropy)
  (polynomial_entity,) = context.sample(
      sample_args, [composition.Polynomial(coeffs)])

  if random.choice([False, True]):
    # Ask for explicit roots.
    if len(solutions) == 1:
      answer = solutions[0]
    else:
      answer = display.NumberList(solutions)

    if polynomial_entity.has_expression():
      equality = ops.Eq(polynomial_entity.expression, 0)
      variable = polynomial_entity.polynomial_variables[0]
    else:
      variable = sympy.Symbol(context.pop())
      equality = ops.Eq(polynomial_entity.handle.apply(variable), 0)
    template = random.choice([
        'Let {equality}. What is {variable}?',
        'Let {equality}. Calculate {variable}.',
        'Suppose {equality}. What is {variable}?',
        'Suppose {equality}. Calculate {variable}.',
        'What is {variable} in {equality}?',
        'Solve {equality} for {variable}.',
        'Find {variable} such that {equality}.',
        'Find {variable}, given that {equality}.',
        'Determine {variable} so that {equality}.',
        'Determine {variable}, given that {equality}.',
        'Solve {equality}.'
    ])
    return example.Problem(
        question=example.question(
            context, template, equality=equality, variable=variable),
        answer=answer)
  else:
    if polynomial_entity.has_expression():
      expression = polynomial_entity.expression
      variable = polynomial_entity.polynomial_variables[0]
    else:
      variable = sympy.Symbol(context.pop())
      expression = polynomial_entity.handle.apply(variable)
    factored = sympy.factor(
        polynomials.coefficients_to_polynomial(coeffs, variable))
    template = random.choice([
        'Factor {expression}.',
    ])
    return example.Problem(
        question=example.question(context, template, expression=expression),
        answer=factored)


def _solve_linear_system(degree, value, sample_args, context=None):
  """Solve linear equations."""
  is_question = context is None
  if context is None:
    context = composition.Context()

  entropy, sample_args = sample_args.peel()

  solutions = []
  if value is not None:
    solutions.append(value)

  extra_solutions_needed = degree - len(solutions)
  if extra_solutions_needed > 0:
    entropies = (entropy / 4) * np.random.dirichlet(
        np.ones(extra_solutions_needed))
    entropies = np.maximum(1, entropies)  # min per-solution entropy
    entropy -= sum(entropies)
    solutions += [number.integer(solution_entropy, True)
                  for solution_entropy in entropies]
  entropy = max(1, entropy)

  variables = [sympy.Symbol(context.pop()) for _ in range(degree)]

  solution_index = 0
  # If we're going to be creating a linear system with constants to replace by
  # handles from other modules, then we need a linear system with constants
  # occurring. Very occasionally this can fail to happen, e.g., "x = -x";
  # normally this while loop will only see one iteration.
  while True:
    equations = linear_system.linear_system(
        variables=variables, solutions=solutions, entropy=entropy,
        non_trivial_in=solution_index)
    constants = ops.number_constants(equations)
    if sample_args.num_modules <= 1 or constants:
      break

  context.sample_by_replacing_constants(sample_args, equations)

  variable = variables[solution_index]
  answer = solutions[solution_index]

  equations = ', '.join([str(equation) for equation in equations])

  if is_question:
    template = random.choice([
        'Solve {equations} for {variable}.',
    ])
    return example.Problem(
        example.question(
            context, template, equations=equations,
            variable=variable),
        answer)
  else:
    return composition.Entity(
        context=context,
        value=answer,
        description='Suppose {equations}.',
        handle=variable,
        equations=equations)


@composition.module(number.is_integer)
def solve_linear_1d(*args, **kwargs):
  return _solve_linear_system(1, *args, **kwargs)


@composition.module(number.is_integer)
def solve_linear_2d(*args, **kwargs):
  return _solve_linear_system(2, *args, **kwargs)


class _PolynomialSequence(object):
  """A sequence given by a polynomial."""

  def __init__(self, variable, entropy, min_degree=1, max_degree=3):
    """Initializes a random polynomial sequence.

    Args:
      variable: Variable to use.
      entropy: Entropy for polynomial coefficients.
      min_degree: Minimum order of polynomial.
      max_degree: Maximum order of polynomial.
    """
    self._degree = random.randint(min_degree, max_degree)
    self._variable = variable
    polynomial = polynomials.sample_with_small_evaluation(
        variable=self._variable, degree=self._degree,
        max_abs_input=self._degree + 2, entropy=entropy)
    self._sympy = polynomial.sympy()

  @property
  def min_num_terms(self):
    """Returns the minimum number of terms to identify the sequence.

    This assumes a human-like prior over types of sequences.

    Returns:
      Integer >= 1.
    """
    return self._degree + 2

  @property
  def sympy(self):
    return self._sympy

  def term(self, n):
    """Returns the `n`th term of the sequence."""
    return self._sympy.subs(self._variable, n)


def sequence_next_term(min_entropy, max_entropy):
  """E.g., "What is the next term in the sequence 1, 2, 3?"."""
  entropy = random.uniform(min_entropy, max_entropy)
  context = composition.Context()
  variable = sympy.Symbol(context.pop())

  sequence = _PolynomialSequence(variable, entropy)
  min_num_terms = sequence.min_num_terms
  num_terms = random.randint(min_num_terms, min_num_terms + 3)
  sequence_sample = [sequence.term(n + 1) for n in range(num_terms)]
  sequence_sample = display.NumberList(sequence_sample)

  template = random.choice([
      'What is next in {sequence}?',
      'What comes next: {sequence}?',
      'What is the next term in {sequence}?',
  ])
  answer = sequence.term(num_terms + 1)

  return example.Problem(
      question=example.question(context, template, sequence=sequence_sample),
      answer=answer)


def sequence_nth_term(min_entropy, max_entropy):
  """E.g., "What is the nth term in the sequence 1, 2, 3?"."""
  entropy = random.uniform(min_entropy, max_entropy)
  context = composition.Context()
  variable = sympy.Symbol(context.pop())

  sequence = _PolynomialSequence(variable, entropy)
  min_num_terms = sequence.min_num_terms
  num_terms = random.randint(min_num_terms, min_num_terms + 3)
  sequence_sample = [sequence.term(n + 1) for n in range(num_terms)]
  sequence_sample = display.NumberList(sequence_sample)

  template = random.choice([
      'What is the {variable}\'th term of {sequence}?',
  ])
  answer = sequence.sympy

  return example.Problem(
      question=example.question(
          context, template, variable=variable, sequence=sequence_sample),
      answer=answer)
