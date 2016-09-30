from golem.dialog_manager import DialogManager
import sys
import traceback
from threading import Thread
from queue import Queue

class MessageQueue(object):
    def __init__(self, config):
        self.queue = Queue()
        self.worker = Worker(queue=self.queue, fn=self.process, num_threads=3)
        self.config = config

    def process(self, uid, message, interface):
        try:
            dialog = DialogManager(config=self.config, uid=uid, interface=interface)
            dialog.process(message) 
        except Exception as err:
            print("!!!!!!!!!!!!!!!! EXCEPTION AT MESSAGE QUEUE !!!!!!!!!!!!!!!", err)
            traceback.print_exc(file=sys.stdout)

class Worker:
    threads = []
    def __init__(self, queue, fn, num_threads):
        self.fn = fn
        for _ in range(num_threads):
            self.threads.append(Thread(target=self.run, args=(queue,)))
            self.threads[-1].deamon = True
            self.threads[-1].start()

    def run(self, queue):
        while True:
            work = queue.get()
            self.fn(*work)
        [t.join() for t in self.threads]

