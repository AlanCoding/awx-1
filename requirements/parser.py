#!/usr/bin/env python3

import argparse
import re


# example string
# asgi-amqp==1.1.3  # FIX: does not support channels 2
line_matcher = re.compile(
    r'^(?P<package>[a-zA-Z0-9-_.\[\]]+)'
    # collectively the specifier and version are optional, case of unpined
    r'('
        r'(?P<specifier>==|>=|<=|>|<)'  # noqa
        r'(?P<version>[0-9.]+)'
    r')?'
    r'\s*(#\s*(?P<comment>.*))?'
)


def strip(filename):
    with open(filename, 'r') as f:
        lines = f.read().split('\n')

    new_text = []
    for line in lines:
        matches = line_matcher.search(line)
        if matches is None and not line or line.startswith('#'):
            new_text.append(line)
            continue
        try:
            package = matches.group('package')
            specifier = matches.group('specifier')
            comment = matches.group('comment')
        except Exception:
            print('Parse error on line :\n{}'.format(line))
            raise

        if comment and comment.strip().startswith('FIX'):
            new_text.append(line)
        else:
            # if the input was already greater-than, then no need to unpin
            if '>' in specifier:
                constraint = package + specifier
            else:
                constraint = package
            if comment:
                new_text.append(constraint + '  #' + comment)
            else:
                new_text.append(constraint)

    with open(filename, 'w') as f:
        f.write('\n'.join(new_text))

    print('Removed versions from {}'.format(filename))



def restore(filename):
    with open(filename.replace('.in', '.txt'), 'r') as f:
        known = f.read()

    version_map = {}
    for line in known.split('\n'):
        matches = line_matcher.search(line)
        if matches is None and not line or line.startswith('#'):
            continue
        try:
            package = matches.group('package')
            version = matches.group('version')
        except Exception:
            print('Parse error on line :\n{}'.format(line))
            raise

        version_map[package] = version

    with open(filename, 'r') as f:
        lines = f.read().split('\n')

    new_text = []
    for line in lines:
        matches = line_matcher.search(line)
        if matches is None and not line or line.startswith('#'):
            new_text.append(line)
            continue
        try:
            package = matches.group('package')
            specifier = '=='
            old_specifier = matches.group('specifier')
            if old_specifier:
                specifier = old_specifier
            comment = matches.group('comment')
        except Exception:
            print('Parse error on line :\n{}'.format(line))
            raise

        try:
            version = version_map[package.lower().replace('_', '-')]
        except KeyError:
            version = version_map[package.lower()]

        new_line = package + specifier + version
        if comment:
            new_line += '  # ' + comment

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
