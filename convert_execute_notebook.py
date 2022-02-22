import os
import nbformat
import sys
import argparse
from nbconvert import PythonExporter
from subprocess import run, PIPE
 
NOTEBOOK_SRC_DIR = './src/notebooks'
 
def convert_and_execute_notebook_to_python(notebookname):
    nb = None
    output = ''
    rc = None
    with open(os.path.join(NOTEBOOK_SRC_DIR, notebookname)) as fh:
        nb = nbformat.reads(fh.read(), nbformat.NO_CONVERT)
    exporter = PythonExporter()
    source, meta = exporter.from_notebook_node(nb)
    source = source.replace("%config Completer.use_jedi = False", "# %config Completer.use_jedi = False")
    source = source.replace("get_ipython().", "# get_ipython().")
    # Get the converted python script name from notebook name
    python_script_path = os.path.join(NOTEBOOK_SRC_DIR, '%s.py' %os.path.splitext(notebookname)[0])
    with open(python_script_path, 'w+') as fh:
        fh.writelines(source)
    # Execute the converted python script
    result = run([sys.executable, python_script_path], stdout=PIPE, stderr=PIPE, universal_newlines=True)
    output = result.stdout
    if result.returncode != 0:
        output += result.stderr
    return result.returncode, output
 
if __name__ == '__main__':
    nb_list = []

    for nbfile in os.listdir(NOTEBOOK_SRC_DIR):
        if nbfile.endswith('.ipynb'):
            nb_list.append(nbfile)
    
    for eachnbfile in nb_list:
        rc, output = convert_and_execute_notebook_to_python(eachnbfile)
        print("Return code:%s" %rc)
        print("Execution Output:%s" %output)
        if rc != 0:
            sys.exit(1)
    sys.exit(0)
