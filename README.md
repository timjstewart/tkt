# A script for automating part of my workflow.


# Configuration

Config file is located at ~/.config/tkt/tkt.conf


An example configuration:

```
[main]
# Where remote repositories are checked out to
local_repository_parent_dir = ~/src

# A regular expression with a group that is used to
# extract the branch name from the remote URL.
branch_name_regex = .*(PROJ-.*)

# Where your org-mode tickets file is.
ticket_file_path = ~/org/tickets_file.org
```

# Example Usage

```
python3 tkt.py --ticket-url http://www.projectmgt.net/tickets/PROJ-252
               --remote-repository-url=https://github.com/timjstewart/flint.git
               --main-branch-name=main
```
