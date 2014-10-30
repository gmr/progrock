Examples
========
The following example will create a process for each CPU core on the system
that it is run on, displaying the :py:class:`progrock.MultiProgress` screen,
using :py:class:`progrock.MultiProgress` as a context manager. The child
processes will iterate 100 times, updating their progress bar and then
sleeping up to 1 second.

.. code:: python

    import multiprocessing
    import progrock
    import random
    import time

    def example_runner(ipc_queue):
        # Update the processes status in its progress box
        progrock.set_status(ipc_queue, 'Running')

        # Increment the progress bar, sleeping up to one second per iteration
        for iteration in range(1, 101):
            progrock.increment(ipc_queue)
            time.sleep(random.random())

    processes = []

    # Create the MultiProgress instance
    with progrock.MultiProgress('Example') as progress:

        # Spawn a process per CPU and append it to the list of processes
        for proc_num in range(0, multiprocessing.cpu_count()):
            processes.append(progress.new_process(example_runner))

        # Wait for the processes to run
        while any([p.is_alive() for p in processes]):
            time.sleep(1)

This example performs the exact same tasks as the previous one, however it does
not use :py:class:`progrock.MultiProgress` as a context manager. In this example
you will notice that the screen must be initialized on startup and shutdown
when done.

.. code:: python

    import multiprocessing
    import progrock
    import random
    import time

    def example_runner(ipc_queue):
        # Update the processes status in its progress box
        progrock.set_status(ipc_queue, 'Running')

        # Increment the progress bar, sleeping up to one second per iteration
        for iteration in range(1, 101):
            progrock.increment(ipc_queue)
            time.sleep(random.random())

    processes = []
    cpu_count = multiprocessing.cpu_count()

    # Create the MultiProgress instance
    progress = progrock.MultiProgress('Example', cpu_count)

    # Initialize the screen
    progress.initialize()

    # Spawn a process per CPU and append it to the list of processes
    for proc_num in range(0, cpu_count):
        processes.append(progress.new_process(example_runner))
        progress.increment_app()
        time.sleep(random.random())

    # Wait for the processes to run
    while any([p.is_alive() for p in processes]):
        time.sleep(1)

    # Shutdown the screen
    progress.shutdown()
