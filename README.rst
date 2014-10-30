progrock
========
The ``progrock.MultiProgress`` class is used in conjunction with the
methods exposed at the module level such as ``progrock.increment`` to
create a full-screen experience allowing the user to track the progress of
individual processes as they perform their work.

|Version| |Downloads| |License|

Installation
------------
progrock may be installed via the Python package index with the tool of
your choice. I prefer pip:

.. code:: bash

    pip install progrock

Documentation
-------------

https://progrock.readthedocs.org

Requirements
------------
There are no requirements outside of the Python standard library.

Screenshot
----------
The following image shows the example code listing in action:

.. image:: http://i.imgur.com/wi9MAdp.png

Example
-------
The following example will create a process for each CPU core on the system
that it is run on, displaying the MultiProgress screen. The child processes
will iterate 100 times, updating their progress bar and then sleeping up to
1 second.

.. code:: python

    import progrock
    import random

    def example_runner(ipc_queue):
        # Update the processes status in its progress box
        progrock.set_status(ipc_queue, 'Running')

        # Increment the progress bar, sleeping up to one second per iteration
        for iteration in range(1, 101):
            progrock.increment(ipc_queue)
            progrock.increment_app(ipc_queue)
            time.sleep(random.random())

    processes = []

    # Create the MultiProgress instance
    steps = multiprocessing.cpu_count() * 100
    with MultiProgress('Example', steps=steps) as progress:

        # Spawn a process per CPU and append it to the list of processes
        for proc_num in range(0, multiprocessing.cpu_count()):
            processes.append(progress.new_process(example_runner))

        # Wait for the processes to run
        while any([p.is_alive() for p in processes]):
            time.sleep(1)

Version History
---------------
Available at https://progrock.readthedocs.org

.. |Version| image:: https://badge.fury.io/py/progrock.svg?
   :target: http://badge.fury.io/py/progrock

.. |Downloads| image:: https://pypip.in/d/progrock/badge.svg?
   :target: https://pypi.python.org/pypi/progrock

.. |License| image:: https://pypip.in/license/progrock/badge.svg?
   :target: https://progrock.readthedocs.org
