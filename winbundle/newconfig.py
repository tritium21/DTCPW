import pathlib

import questionary
import toml


def new_config(path):
    path = pathlib.Path(path).resolve()
    data = {}
    if path.is_file():
        data = toml.loads(path.read_text(encoding='utf8'))
    elif path.is_dir():
        path = path / 'pyproject.toml'
    project = data.get('project', {})
    if not project:
        data['project'] = {}
        data['project']['name'] = questionary.text("What is the project name?").ask()
        data['project']['version'] = questionary.text("What is the current version?").ask()
        requirements = path.parent / 'requirements.txt'
        if requirements.is_file():
            reqs = requirements.read_text(encoding='utf8')
            print(reqs)
            use_reqs = questionary.confirm("Are these runtime dependencies correct?").ask()
            if use_reqs:
                data['project']['dependencies'] = [s.strip() for s in reqs.splitlines()]
        if not data['project'].get('dependencies'):
            data['project']['dependencies'] = [
                s.strip()
                for s in questionary.text("What are the runetime dependencies?", multiline=True).ask().splitlines()
            ]
        scripts = {}
        gui_scripts = {}
        while True:
            cmd = questionary.text(
                "What is the command for the entry point (in package.module:callable format)?",
                instruction="Enter for none or done"
            ).ask()
            if not cmd:
                break
            name = questionary.text("What is the name of entry point? It will turn into <NAME>.exe").ask()
            icon = questionary.text("(Optional) What is the icon file relative to this directory?").ask()
            gui = questionary.confirm("Is this a GUI entry point??").ask()
            if icon:
                script = {name: f"{cmd} [icon={icon}]"}
            else:
                script = {name: cmd}
            if gui:
                gui_scripts.update(script)
            else:
                scripts.update(script)
        if scripts:
            data['project']['scripts'] = scripts
        if gui_scripts:
            data['project']['gui-scripts'] = gui_scripts
    data['tool'] = {}
    data['tool']['winbundle'] = {}
    src = questionary.text("Where are the source files, relative to this directory?", multiline=True).ask()
    data['tool']['winbundle']['src'] = [s.strip() for s in src.strip().splitlines()]
    data['tool']['winbundle']['need_tkinter'] = questionary.confirm("Is tkinter required?").ask()
    py_version = questionary.text(
        "(Optional) What python version is required (X.Y.Z format)?",
        instruction="Press enter to use the version of python used to run this."
    ).ask()
    if py_version:
        data['tool']['winbundle']['py_version'] = py_version
    machine = questionary.select(
        "(Optional) What machine type is required?",
        instruction="Choose default to use the machine type currently executing.",
        choices=[
            'default',
            'win32',
            'amd64',
        ]
    ).ask()
    if machine != 'default':
        data['tool']['winbundle']['machine'] = machine
    path.write_text(toml.dumps(data))
