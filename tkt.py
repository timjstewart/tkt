import io
import argparse
import configparser
import re
import sys
import subprocess

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Any


@dataclass
class TicketConfig:
    # Must be in configuration file
    local_repository_parent_dir: Path
    branch_name_regex: re.Pattern
    ticket_file_path: Path

    # May be in configuration file or supplied on the command line
    ticket_url: Optional[str]
    remote_repository_url: Optional[str]
    main_branch_name: Optional[str]

    @staticmethod
    def combine(lhs: 'TicketConfig', rhs: 'TicketConfig') -> 'TicketConfig':
        return TicketConfig(
            local_repository_parent_dir=(
                lhs.local_repository_parent_dir or
                rhs.local_repository_parent_dir
                ).expanduser(),
            branch_name_regex=(
                lhs.branch_name_regex or
                rhs.branch_name_regex
                ),
            ticket_file_path=(
                lhs.ticket_file_path or
                rhs.ticket_file_path
                ).expanduser(),
            ticket_url=(
                lhs.ticket_url or
                rhs.ticket_url
                ),
            remote_repository_url=(
                lhs.remote_repository_url or
                rhs.remote_repository_url
                ),
            main_branch_name=(
                lhs.main_branch_name or
                rhs.main_branch_name
                )
        )

    def validate(self) -> 'TicketConfig':
        if not self.remote_repository_url:
            raise Exception("remote_repository_url was not configured")
        if not self.branch_name_regex:
            raise Exception("branch_name_regex was not configured")
        if not self.local_repository_parent_dir.expanduser().is_dir():
            raise Exception("directory not found: "
                            f"{self.local_repository_parent_dir}.")
        if not self.ticket_file_path.expanduser().is_file():
            raise Exception("file not found: "
                            f"{self.ticket_file_path}.")
        return self

    def get_branch_name(self) -> str:
        match = self.branch_name_regex.search(self.ticket_url)
        if match and match.group(1):
            return match.group(1)
        raise Exception(f"the regex '{self.branch_name_regex.pattern}' did "
                        f"not match the ticket URL: '{self.ticket_url}'")

    def get_source_dir(self) -> Path:
        regex = re.compile(r".*/(.*)")
        repo_dir = regex.search(self.remote_repository_url).group(1)
        return Path(self.local_repository_parent_dir / repo_dir)


def load_config() -> Optional[TicketConfig]:
    def compile_re(s: Optional[str]) -> re.Pattern:
        if not s:
            raise Exception("empty regex")
        result = re.compile(s)
        return result

    def read_optional(cfg, key, name) -> Optional[str]:
        if name in cfg[key]:
            value = cfg[key][name]
            if value:
                return value
        return None

    def read_required(cfg, key, name) -> str:
        value = cfg[key][name]
        if value:
            return value
        raise KeyError(name)

    try:
        path = get_config_path()
        cfg = configparser.ConfigParser()
        cfg.read(path)
        KEY = 'main'
        return TicketConfig(
            local_repository_parent_dir=Path(
                read_required(cfg, KEY, "local_repository_parent_dir")
            ),
            branch_name_regex=compile_re(
                read_optional(cfg, KEY, "branch_name_regex")
            ),
            ticket_file_path=Path(
                read_required(cfg, KEY, "ticket_file_path")
            ),
            ticket_url=read_optional(cfg, KEY, "ticket_url"),
            remote_repository_url=read_optional(
                cfg, KEY, "remote_repository_url"),
            main_branch_name=read_optional(cfg, KEY, "remote_repository_url")
        )
    except KeyError as ex:
        print(f"config file: {path} is missing entry: {ex}")
        return None
    except Exception as ex:
        print(f"config file error: {ex}")
        return None


def get_config_path() -> Path:
    path = Path(Path.home() / ".config" / "tkt" / "tkt.conf")
    if not path.is_file():
        raise Exception(f"config file not found: {path}")
    return path


def parse_args(args: List[str]) -> TicketConfig:
    parser = argparse.ArgumentParser(description='Start work on a new ticket.')

    parser.add_argument(
        '--local-repository-parent-dir',
        type=str,
        metavar='p',
        required=False,
        help='The path under which the git repository will be cloned.'
    )

    parser.add_argument(
        '--branch-name-regex',
        type=str,
        metavar='r',
        required=False,
        help=('A regular expression used to extract the branch name from the '
              'ticket URL.')
    )

    parser.add_argument(
        '--ticket-file-path',
        type=str,
        metavar='f',
        required=False,
        help='The path to the org file where ticket information is appended.'
    )

    parser.add_argument(
        '--ticket-url',
        type=str,
        metavar='t',
        required=True,
        help='The URL to the ticket.'
    )

    parser.add_argument(
        '--remote-repository-url',
        type=str,
        metavar='u',
        required=False,
        help=("The URL to remote repository that the ticket's "
              "work will be done in.")
    )

    parser.add_argument(
        '--main-branch-name',
        type=str,
        metavar='b',
        required=False,
        help=("The name of the main branch that ticket branches "
              "should be created from.")
    )

    result = parser.parse_args()

    return TicketConfig(
            local_repository_parent_dir=(result.local_repository_parent_dir),
            branch_name_regex=(result.branch_name_regex),
            ticket_file_path=(result.ticket_file_path),
            ticket_url=(result.ticket_url),
            remote_repository_url=(result.remote_repository_url),
            main_branch_name=(result.main_branch_name),
        )


def get_config(args: List[str]) -> TicketConfig:
    file_cfg = load_config()
    if not file_cfg:
        sys.exit(1)
    args_cfg = parse_args(args)
    try:
        return TicketConfig.combine(file_cfg, args_cfg).validate()
    except Exception as ex:
        print(f"error: {ex}")
        sys.exit(1)


def run_git(*args: List[Any],
            pwd: Optional[Path] = None,
            capture_output: bool = True,
            show_error_output: bool = True
            ) -> bool:
    full_args = ["git"]
    if pwd:
        full_args.extend(["-C", str(pwd)])
    full_args.extend(args)
    result = None
    try:
        result = subprocess.run(full_args, capture_output=capture_output)
        result.check_returncode()
        return True
    except Exception as ex:
        if show_error_output:
            print(f"error: {result.stderr.decode('utf-8')} {ex}")
        return False


def clone_repository(remote_url: str,
                     parent_dir: Path) -> bool:
    print("attempting to clone repository...")
    result = run_git("clone", remote_url, pwd=parent_dir,
                     show_error_output=False)
    return result


def pull_repository(remote_url: str,
                    parent_dir: Path) -> bool:
    print("attempting to pull repository...")
    regex = re.compile(r".*/(.*)")
    repo_dir = regex.search(remote_url).group(1)
    repo_dir = Path(parent_dir / repo_dir)
    result = run_git("pull", pwd=repo_dir, capture_output=True,
                     show_error_output=False)
    return result


def checkout_branch(remote_url: str,
                    main_branch_name: str,
                    parent_dir: Path) -> bool:
    regex = re.compile(r".*/(.*)")
    repo_dir = regex.search(remote_url).group(1)
    repo_dir = Path(parent_dir / repo_dir)

    return run_git("checkout", main_branch_name, pwd=repo_dir)


def create_branch(remote_url: str,
                    branch_name: str,
                    parent_dir: Path) -> bool:
    regex = re.compile(r".*/(.*)")
    repo_dir = regex.search(remote_url).group(1)
    repo_dir = Path(parent_dir / repo_dir)

    return run_git("checkout", "-b", branch_name, pwd=repo_dir,
                   show_error_output=True)

def append_to_ticket_file(*args, **kwargs) -> None:
    s = io.StringIO()
    s.write(f"""** TODO Ticket: {kwargs['ticket_name']}
   Source: {kwargs['source_dir'] }
   Ticket: {kwargs['ticket_url'] }
   Remote: {kwargs['remote_url'] }
""")
    with Path.open(kwargs['ticket_file_path'], 'a') as out:
        out.write(s.getvalue())
    print(f"updated: {kwargs['ticket_file_path']}")


def main():
    try:
        cfg = get_config(sys.argv[1:])
        branch_name = cfg.get_branch_name()

        (clone_repository(remote_url=cfg.remote_repository_url,
                          parent_dir=cfg.local_repository_parent_dir)
         or pull_repository(remote_url=cfg.remote_repository_url,
                            parent_dir=cfg.local_repository_parent_dir))

        checkout_branch(remote_url=cfg.remote_repository_url,
                        main_branch_name=cfg.main_branch_name,
                        parent_dir=cfg.local_repository_parent_dir)

        (create_branch(remote_url=cfg.remote_repository_url,
                      branch_name=cfg.get_branch_name(),
                      parent_dir=cfg.local_repository_parent_dir) or
        checkout_branch(remote_url=cfg.remote_repository_url,
                        main_branch_name=cfg.get_branch_name(),
                        parent_dir=cfg.local_repository_parent_dir))
        append_to_ticket_file(
            ticket_file_path=cfg.ticket_file_path,
            remote_url=cfg.remote_repository_url,
            ticket_name=cfg.get_branch_name(),
            ticket_url=cfg.ticket_url,
            source_dir=cfg.get_source_dir()
            )
    except Exception as ex:
        print(f"error: {ex}, {type(ex)}")


if __name__ == '__main__':
    main()
