"""
Generates a conditional probability table by exercise, based on analytics
cards. Specifically, we compute

Pr(X_i = x_i | X_j = x_j),

where i, j represent exercises, X_i, X_j are binary random variables
represnting correctness, and x_i, x_j represent correctness values.

The quantities we are then interested in are

Y_jk = sum_i Pr(X_i = 1 | X_j = k),

i.e. the average accuracy on analytics cards given we answered exercise j
with correctness k.
"""

import argparse
import csv
import sys
import time

import numpy as np
import matplotlib.pyplot as plt


def read_data(filename):
    # BigQuery can't handle sorting so we do it here
    data = {}

    with (sys.stdin if filename is None else open(filename, 'r')) as f:
        reader = csv.reader(f)
        header = reader.next()

        # because I keep forgetting which order the rows are in
        user_id_index = header.index('user_id')
        exercise_index = header.index('exercise')
        correct_index = header.index('correct')
        time_done_index = header.index('time_done')

        # break down analytics cards by user_id
        i = 0
        for row in reader:
            user_id = row[user_id_index]
            exercise = row[exercise_index]
            correct = 1 if row[correct_index] == 'true' else 0
            time_done = int(row[time_done_index])
            if user_id not in data:
                data[user_id] = []
            data[user_id].append((time_done, exercise, correct))
            i += 1
            if i % 500000 == 0:
                print 'Processed %d' % i

    # we remove the timestamp and turn everything into a list
    return [[(e, c) for t, e, c in sorted(row)] for row in data.values()]


def get_exercises(data, min_problems):
    exercise_cnt = {}
    for row in data:
        for e, c in row:
            if e not in exercise_cnt:
                exercise_cnt[e] = 1
            else:
                exercise_cnt[e] += 1

    # filter out the retired/experimental exercises
    exercises = []
    for e in exercise_cnt:
        cnt = exercise_cnt[e]
        if cnt >= min_problems:
            exercises.append(e)
    exercises.sort()

    return exercises


def graph_by_difficulty(prob_all, min_problems):
    prob_all.sort()
    prob_all = np.array(prob_all)
    p = prob_all[:, 0]
    p0 = prob_all[:, 1]
    p1 = prob_all[:, 2]

    plt.figure()

    plt.title('Conditional Probabilities on Analytics Cards')
    plt.xlabel('Exercise (sorted by average accuracy)')
    plt.ylabel('Accuracy')
    plt.plot(p, label='p_global')
    plt.plot(p0, label='p_0')
    plt.plot(p1, label='p_1')
    plt.legend(loc='upper center')

    filename = 'conditional-prob-%d.png' % min_problems
    print 'Saving... %s' % filename
    plt.savefig(filename)
    # plt.show()
    plt.clf()


def compute_and_write(data, min_problems, filename):
    """ Write out the results. Each row is given by:

    exercise,prob0,prob1.

    Here, probk is the average probability of getting analytics card right,
    given that we got correct == k on the current exercise.
    """
    exercises = get_exercises(data, min_problems)
    exercise_to_index = {}
    for i, e in enumerate(exercises):
        exercise_to_index[e] = i

    n = len(exercises)
    print 'Num exercises:', n

    # pk[i][0][j] / pk[i][1][j] is Pr(X_j = 1 | X_i = k)
    # the two middle indicies 0 and 1 represent the number correct and total
    p0 = np.zeros((n, 2, n))
    p1 = np.zeros((n, 2, n))

    # global probabilities for each exercise
    p = np.zeros((n, 2))

    for row in data:
        prev_e, prev_c = None, False
        for e, c in row:
            # skip exercises that were filtered out
            if e not in exercise_to_index:
                continue

            j = exercise_to_index[e]
            p[j][0] += c
            p[j][1] += 1

            # look at our current pair!
            if prev_e:
                i = exercise_to_index[prev_e]
                if prev_c == 0:
                    p0[i][0][j] += c
                    p0[i][1][j] += 1
                else:
                    p1[i][0][j] += c
                    p1[i][1][j] += 1
            prev_e, prev_c = e, c

    print 'Count, all:', int(np.sum(p) / 2)
    print 'Count, prev 0:', int(np.sum(p0) / 2)
    print 'Count, prev 1:', int(np.sum(p1) / 2)

    """
    with open('tmp.txt', 'w') as f:
        f.write(str(p0) + '\n')
        f.write(str(p1) + '\n')
    """
    print np.array(sorted([np.sum(p0[i][1]) for i in xrange(n)]))
    print np.array(sorted([np.sum(p1[i][1]) for i in xrange(n)]))

    # A list of (global_prob, prob0, prob1)
    prob_all = []

    # Write results
    with open(filename, 'w') as f:
        for i, e in enumerate(exercises):
            prob0 = 1.0 * (np.sum(p0[i][0]) / np.sum(p0[i][1]))
            prob1 = 1.0 * (np.sum(p1[i][0]) / np.sum(p1[i][1]))
            f.write('%s,%.5f,%.5f\n' % (e, prob0, prob1))
            prob_all.append((p[i][0] / p[i][1], prob0, prob1))
            if prob0 < 0.2:
                print e, i
                print p[i][0] / p[i][1], prob0, prob1
                print p[i][1], np.sum(p0[i][1]), np.sum(p1[i][1])

    # Plot overall exercise accuracy by these values
    graph_by_difficulty(prob_all, min_problems)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('-f', '--file',
        help='input file (default is stdin)')
    parser.add_argument('-m', '--min-problems',
        help='minimum number of samples for filtering exercises',
        type=int, default=10000)

    args = parser.parse_args()

    filename = args.file
    min_problems = args.min_problems

    # run!
    start = time.time()
    data = read_data(filename)
    print 'Done reading input, elapsed: %f' % (time.time() - start)
    compute_and_write(data, min_problems, 'table.csv')
    print 'Done computing and writing, elapsed: %f' % (time.time() - start)


if __name__ == '__main__':
    main()
