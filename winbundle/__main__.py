import argparse
import pathlib
import sys

import winbundle
import winbundle.newconfig


def build(args):
    config = args.pop('config')
    builder = winbundle.Builder.from_path(config)
    return builder.make_bundle(**args)


def new(args):
    config = args.pop('config')
    return winbundle.newconfig.new_config(config)

def main(argv=None):
    name = f'{sys.executable} -m winbundle' if __name__ == '__main__' else None
    parser = argparse.ArgumentParser(name)

    def help_and_exit(args):
        parser.print_help()
        return 1

    subparsers = parser.add_subparsers()
    build_parser = subparsers.add_parser('build')
    build_parser.add_argument(
        'config',
        default='pyproject.toml',
        type=pathlib.Path
    )
    build_parser.add_argument(
        '--compile', '-c',
        help="Compile python files to bytecode",
        action='store_true',
    )
    build_parser.add_argument(
        '--optimize', '-o',
        choices=['-1', '0', '1', '2'],
        help="Optimize compiled bytecode - ignored if not -c",
        type=int,
        default=-1
    )
    build_parser.add_argument(
        '--release', '-r',
        action='store_true',
        help="Make a relase (don't just build)",
    )
    build_parser.add_argument(
        '--zip', '-z',
        action='store_true',
        help='Also zip release',
        dest='make_zip'
    )
    build_parser.set_defaults(func=build)
    new_parser = subparsers.add_parser('new')
    new_parser.add_argument(
        'config',
        default='pyproject.toml',
        type=pathlib.Path
    )
    new_parser.set_defaults(func=new)
    args = parser.parse_args(argv)
    args = vars(args)
    func = args.pop('func', help_and_exit)
    return func(args)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
