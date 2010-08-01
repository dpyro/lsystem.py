#!/usr/bin/env python

from lepl import *
import numpy as np
import getopt
import hurry.filesize
import math
import os.path
import pygame
import sys

class LSystem(object):
    
    class Turtle(object):
        """ A turtle-graphics style drawing class for LSystem.

        Rather than directly drawing lines onto a canvas,
        Turtle instead accumulates a numpy array of point pairs
        such that [p1a, p1b, ...] where a line is p1a -> p1b.
        """
        def __init__(self):
            self.pos = (0, 0)
            self.angle = 0
            self.states = []
            self.vectors = np.empty([0, 2], float)

        def turn(self, angle):
            """ Turn the turtle `angle` degrees. """
            self.angle += math.radians(angle)

        def move(self, draw=True):
            """ Move the turtle forward one unit."""
            x_move = math.cos(self.angle)
            y_move = math.sin(self.angle)
            old_x, old_y = self.pos
            new_x, new_y = (old_x + x_move, old_y + y_move)
            self.pos = new_x, new_y
            if draw:
                add_vec = [[old_x, old_y], [new_x, new_y]]
                self.vectors = np.append(self.vectors, add_vec, axis=0)

        def push(self):
            """ Save the current state onto the state stack. """
            self.states.append((self.pos, self.angle))

        def pop(self):
            """ Get the old state from the state stack. """
            new_pos, new_angle = self.states.pop()
            self.pos = new_pos
            self.angle = new_angle

        def get_vectors(self):
            """ Return the numpy array of lines.
            
            Each line consists of a pair of points in the array.
            """
            return self.vectors

        def clear_vectors(self):
            """ Clear the accumulated numpy array of lines. """
            self.vectors = np.empty([0, 2], int)

    
    @staticmethod
    def _build_parser():
        right_arrow = Literal('->')
        comment = ~(Space()[:] & '#' & SkipTo(Newline()))
        empty_line = ~(Space()[:] & Newline())
        rest_of_line = comment | Newline()
        with DroppedSpace():
            angle = ~Literal('angle') & ~Literal(':') & ((SignedEFloat() >> float) > 'angle') & ~rest_of_line
            thickness = ~Literal('thickness') & ~Literal(':') & ((UnsignedInteger() >> int) > 'thickness') & ~rest_of_line
            start = (Word() > 'start') & ~rest_of_line
            rule = (((Word() > 'from') & ~right_arrow & (Word() > 'to') & ~rest_of_line) > make_dict) > 'rule'
        line = angle | thickness | rule | start | comment | empty_line
        return line[:]

    @classmethod
    def load_file(cls, filepath):
        """ Return an LSystem constructed from the contents of `filepath`.
        
        See the included *.ls files for examples.
        """
        with open(filepath, 'r') as f:
            data = f.read()

        parser = cls._build_parser()
        p = parser.parse(data)
        start = None
        angle = 90
        thickness = 1
        rules = {}
        for key, val in p:
            if key == 'start':
                start = val
            elif key == 'angle':
                angle = val
            elif key == 'thickness':
                thickness = val
            elif key == 'rule':
                rule_from = val['from']
                rule_to = val['to']
                rules[rule_from] = rule_to
        
        ls = cls(start, rules, angle, thickness)
        return ls


    def __init__(self, axiom, rules=None, angle=90, thickness=1):
        """Create a new LSystem with the given axiom and rules.

        Arguments:
        * `axiom`     -- the initial state of the system
        * `rules`     -- a dict where {'F': 'FF'} => "F->FF"
        * `angle`     -- the angle to use when making turns with "+" or "-"
        * `thickness` -- the thickness of the rendered lines
        """
        self.angle = angle
        self.thickness = thickness
        self.axiom = axiom
        self.state = axiom
        self.n = 0
        self.rules = rules
        self.turtle = LSystem.Turtle()

    def step(self, iter=1):
        """ Advance the simulation for `iter` iterations. """
        for i in xrange(iter):
            self.turtle.clear_vectors()
            symbols = {'+': ('turnleft',     lambda t: t.turn(-self.angle)),
                       '-': ('turnright',    lambda t: t.turn(self.angle)),
                       'F': ('forward',      lambda t: t.move()),
                       'f': ('skip_forward', lambda t: t.move(False)),
                       '[': ('push_state',   lambda t: t.push()),
                       ']': ('pop_state',    lambda t: t.pop())}
            
            # advance one state
            self.state = ''.join([self.rules.get(x, x) for x in self.state])
            
            for c in self.state:
                if c in symbols:
                    desc, func = symbols[c]
                    func(self.turtle)

            self.n += 1
    
    def step_to(self, n):
        """ Advance the simulation to iteration `n`. """
        assert n >= self.n
        self.step(n - self.n)

    def reset(self):
        """ Reset the simulation to its original state (`n=0`). """
        self.turtle.clear_vectors()
        self.state = self.axiom
        self.n = 0

    def get_vectors(self):
        """ Return the turtle's accumulated numpy array of lines.

        Each line consists of a pair of points in the array.
        """
        return self.turtle.get_vectors()

    def _get_vector_bounds(self):
        v = self.get_vectors()
        maxs = v.max(axis=0)
        mins = v.min(axis=0)
        return (mins[0], mins[1], maxs[0], maxs[1])
        
    def write_png(self, filename):
        """ Render the current iteration `n` to `filename` as a PNG. """
        x_mul = y_mul = 5
        buffer_space = 10
        x_min, y_min, x_max, y_max = self._get_vector_bounds()
        width  = (x_max - x_min) * x_mul + buffer_space * 2
        height = (y_max - y_min) * y_mul + buffer_space * 2
        x_offset = -x_min * x_mul + buffer_space
        y_offset = -y_min * y_mul + buffer_space
        
        s = pygame.Surface((width, height))
        c = pygame.Color(0, 0, 0)
        num_v = len(self.get_vectors())
        for i in range(0, num_v, 2):
            p1 = self.get_vectors()[i]
            p2 = self.get_vectors()[i + 1]
            x1, y1 = p1
            x2, y2 = p2
            x1 = round(x1) * x_mul + x_offset
            x2 = round(x2) * x_mul + x_offset
            y1 = round(y1) * y_mul + y_offset
            y2 = round(y2) * y_mul + y_offset
            hue = (float(i) / num_v) * 360
            c.hsla = (hue, 50, 50, 100)
            pygame.draw.line(s, c, (x1, y1), (x2, y2), self.thickness)
        pygame.image.save(s, filename)

def print_usage():
    print "USAGE: %s file.ls n" % sys.argv[0]

def _parse_args():
    optlist, args = getopt.gnu_getopt(sys.argv[1:], 'v', ['verbose'])

    verbose = False
    for optarg, optval in optlist:
        if optarg == '-v' or optarg == '--verbose':
            verbose = True

    if len(args) != 2:
        print_usage()
        sys.exit(0)

    infile = args[0]
    filef, ext = os.path.splitext(infile)
    outfile = filef + ".png"
    
    num_str = args[1]
    num_args = num_str.split(',')
    nums = []
    for num_arg in num_args:
        n = int(num_arg)
        if n > 0:
            nums.append(n)
        elif n < 0:
            nums.remove(-n)
        else:
            print_usage()
            die(2)
    assert len(nums) > 0
    nums.sort()

    return (infile, outfile, nums, verbose)

if __name__ == '__main__':
    
    infile, outfile, nums, verbose = _parse_args()

    ls = LSystem.load_file(infile)
    for n in nums:
        if verbose:
            print "Advancing simulation to n = %d" % n
        ls.step_to(n)
        
        if len(nums) > 1:
            outfile = os.path.splitext(infile)[0] + '_' + str(n) + ".png"

        if verbose:
            print "Rendering..."
        ls.write_png(outfile)
        filesize = hurry.filesize.size(os.stat(outfile).st_size)
        print "Wrote out %s bytes to %s" % (filesize, outfile)


