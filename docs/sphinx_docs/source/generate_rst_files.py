import os

def generate_rst_file_for_module(file_name, output_directory):
    """
    Generate an RST file for a given Python module.

    :param str file_name: The name of the Python file (without the `.py` extension).
    :param str output_directory: The directory where the RST file will be generated.
    """
    rst_file_path = os.path.join(output_directory, f'{file_name}.rst')
    with open(rst_file_path, 'w') as rst_file:
        # Write file name and underline
        rst_file.write(f'{file_name}\n')
        rst_file.write('=' * len(file_name) + '\n\n')
        
        # Write Sphinx directives
        rst_file.write(f'.. automodule:: {file_name}\n')
        rst_file.write('   :members:\n')
        rst_file.write('   :undoc-members:\n')
        rst_file.write('   :show-inheritance:\n') 

def generate_all_rst_files(directory, output_directory):  
    """
    Generate RST files for all Python files in a directory and its subdirectories.

    :param str directory: The source directory containing Python files.
    :param str output_directory: The directory where the RST files and index will be generated.
    """
    # Create or append to the index.rst file
    index_rst_file_path = os.path.join(output_directory, "index.rst")

    # Open index.rst for writing
    with open(index_rst_file_path, 'w') as index_rst_file:
        index_rst_file.write(f".. mdinclude:: ../../../README.md\n")
        index_rst_file.write(f".. toctree::\n   :maxdepth: 2\n\n")
        
        # Recursively process directories
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.py') and file != '__init__.py':
                    # Get the relative module name
                    relative_path = os.path.relpath(root, directory)
                    file_name = os.path.splitext(file)[0]
                    
                    generate_rst_file_for_module(file_name, output_directory)
                    index_rst_file.write(f"   {file_name}\n")

# Starting point
output_directory = os.getcwd()  # Specify your output directory
os.makedirs(output_directory, exist_ok=True)  # Create the output directory if it doesn't exist
generate_all_rst_files('../../../src', output_directory)