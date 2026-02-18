Installation
------------

.. code-block:: console

   $ pip install vws-python-mock

This requires Python |minimum-python-version|\+.

Faster installation
~~~~~~~~~~~~~~~~~~~

This package depends on `PyTorch`_, which pip installs from PyPI as a large CUDA-enabled build (~873 MB) even on CPU-only machines.
To get a much smaller CPU-only build (~200 MB, no CUDA dependencies), install ``torch`` and ``torchvision`` from PyTorch's CPU index before installing this package:

.. code-block:: console

   $ pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
   $ pip install vws-python-mock

If you manage dependencies with ``uv``, add the following to your ``pyproject.toml`` instead:

.. code-block:: toml

   [[tool.uv.index]]
   name = "pytorch-cpu"
   url = "https://download.pytorch.org/whl/cpu"
   explicit = true

   [tool.uv.sources]
   torch = { index = "pytorch-cpu" }
   torchvision = { index = "pytorch-cpu" }

.. _PyTorch: https://pytorch.org
