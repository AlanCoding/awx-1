#!/usr/bin/env python3

import argparse


def strip(filename):
    with open(filename, 'r') as f:
        lines = f.read().split('\n')

    new_text = []
    for line in lines:
        cmp = None
        for potential in ('==', '<=', '>='):
            if potential in line:
                cmp = potential
        if cmp:
            package, remainder = line.split(cmp)
            comment = ''
            if '#' in line:
                version, comment = remainder.split('#')
                if comment.strip().startswith('FIX'):
                    new_text.append(line)
                else:
                    new_text.append(package + '  #' + comment)
            else:
                new_text.append(package)
        else:
            new_text.append(line)

    with open(filename, 'w') as f:
        f.write('\n'.join(new_text))

    print('Removed versions from {}'.format(filename))



def restore(filename):
    with open(filename.replace('.in', '.txt'), 'r') as f:
        known = f.read()

    version_map = {}
    for line in known.split('\n'):
        if '==' not in line:
            continue
        package, remainder = line.split('==')
        if ' ' in remainder:
            version, _ = remainder.split(' ', 1)
        else:
            version = remainder
        version_map[package] = version

    with open(filename, 'r') as f:
        lines = f.read().split('\n')

    new_text = []
    for line in lines:
        cmp = None
        for potential in ('==', '<=', '>='):
            if potential in line:
                cmp = potential
        if cmp and cmp in line:
            package, remainder = line.split(cmp, 1)
            if '#' in remainder:
                version, stuff = remainder.split('#')
            else:
                stuff = ''
        elif '  #' in line:
            package, stuff = line.split('  #')
        elif '#' in line or not line:
            new_text.append(line)
            continue
        else:
            package = line
            stuff = ''

        new_line = (
            package + '==' +
            version_map[package.lower().replace('_', '-')]
        )
        if stuff:
            new_line += '  #' + stuff

        new_text.append(new_line)

    with open(filename, 'w') as f:
        f.write('\n'.join(new_text))

    print('Applied new fixed versions to {}'.format(filename))


parser = argparse.ArgumentParser()
parser.add_argument(
    'action', type=str, choices=('strip', 'restore'),
    help=(
        'The action to do. Strip removes versions from the file unless marked '
        'with FIX in a comment. Restore copies versions from the .txt version '
        'back into the file.'
    )
)
parser.add_argument(
    'target', type=str,
    help='The .in file to do the strip or restore on. Will be in-place operation.'
)


args = parser.parse_args()


if args.action == 'strip':
    strip(args.target)
elif args.action == 'restore':
    restore(args.target)
else:
    parser.print_help()
