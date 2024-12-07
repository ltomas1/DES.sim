# District Energy System(DES)

This project uses the mosaik package to simulate heat pump in conjuction with a CHP unit to meet the heat and electricity demand of a housing district.

## Installation

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
### Installing dependencies
Install the recommended dependencies with:
```
pip install . docs

```
## Documentation

The documentation for the individual models is available [here](docs\sphinx_docs\source\index.rst)

## Recommended vscode-extensions
- GitLens -Git supercharged: Nice graphical git support
- autopep8: Autoformatting in pep8. Install and press (strg+alt+F)
- Better Comments: Highlighting of comments syntax
- Code Spell Checker: Spelling checker
- Drawio.io Integration: UML-Diagrams, etc. in vs-code
- Edit csv: Editing csv files like tables in excel
- Rainbow CSV: Color highlighting in csv files
- autoDocstring: Python Docstring generator (Generates Docstrings in different styles (Google, sphinx, etc...))

## Note:
**src** Folder: 
- Do not rename it to "code". It will cause name clashes with the internal python module "code".