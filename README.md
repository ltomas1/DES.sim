# Template_for_new_projects

## Getting started

To get started first create a new conda env with:
```
conda create --name myenv python=3.10.13
```
Second activate the environment and install the dependencies out of the pyproject.toml file:
```
conda activate myenv
pip install .
```
After that you can run the script with:
```
python src/main.py
```

## Purpose of this repo
This repo is an template how to structure future repos.
It is structured in three different folders:

- data: All data of your project should be stored here. Configs, inputs and outputs
- docs: Here your repo should be documented. UML-diagrams, docs with sphinx or literature
- src: In here the code is located

To start with a new repo, it is important to consider what is needed. It is important to have a clear structure and to adapt it to the needs of the project again and again during development. For the sake of clarity, an object-orientated approach is recommended. 

For example, a small project does not necessarily need a logger or documentation with Sphinx. Also, not every project needs unitesting.

## Creating docs-html with sphinx 
First you need to install the recommended dependencies with:
```
pip install . docs
```
Afterwards start the documentation with:
```
cd docs
mkdir sphinx_docs
cd sphinx_docs
sphinx-quickstart
```
After that you need to modify the conf.py to include your code - modules and the docstrings. For this please add teh path to the modules that should be imported and the extensions you prefer.
```
#paths to search the modules
sys.path.insert(0, os.path.abspath('..\\..\\..\\src'))

#add all the extensions. For example:
extensions = [
       'sphinx.ext.autodoc',
       'sphinx.ext.autosummary',
       'sphinx.ext.coverage',
        'sphinx.ext.napoleon',
        'm2r2',
       # other extensions...
   ]

#change your doc theme, for example to: 
html_theme = "sphinx_rtd_theme"

#more settings of the docs
...
```
Generate all the .rst-files for the different modules with the script generate_rst_files.py (This script is not included in sphinx and has to be copied out of this repo for other projects)
```
cd source
python generate_rst_files.py
```
Add further modifications by hand or generate the docs with:
```
cd ..
make html
```
After that the documentation ca be visited by opening: "docs/sphinx_docs/build/html/index.html


## Minimal Example
The example in this repo branch shows how a dice can be modelled and rolled

## Branches of this repo
In different Branches are different minimal examples for small code projects. The branches are:

-"main": Minimal example with a rolling dice
-"dev_network_graph": Minimal example for an explicit calculation of a small mass flow network, using the module "networkx" to have a graph representation

## Special files
- .gitignore: Defines what should not by synchronized with git
- pyproject.toml: Here are all dependencies and the repo information are stored. It is also possible to define optional dependencies for development or docs (see the project.toml file)

## Logging
Logging is a means of tracking events that happen when some software runs. The software’s developer adds logging calls to their code to indicate that certain events have occurred. To achieve this a logging configuration is added in this repo and a function to setup the logger is added. This function only needs to run once to create the logger out of the config.

# Helpful tricks and vscode-extensions for coding:
Tricks:
- Press "F2" to rename all instances of a variable 
- Fast debugging "shift+space" of marked code, if the shortcut "Debug: Evaluate in debug mode" is set
- Run "conda init powershell" in the terminal to see the active environment in your powershell

Extensions:
- GitLens -Git supercharged: Nice graphical git support
- autopep8: Autoformatting in pep8. Install and press (strg+alt+F)
- Better Comments: Highlighting of comments syntax
- Code Spell Checker: Spelling checker
- Drawio.io Integration: UML-Diagrams, etc. in vs-code
- Edit csv: Editing csv files like tables in excel
- Rainbow CSV: Color highlighting in csv files
- autoDocstring: Python Docstring generator (Generates Docstrings in different styles (Google, sphinx, etc...))

src Folder: 
- Do not rename it to "code". It will cause name clashes with the internal python module "code".



