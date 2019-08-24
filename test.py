import zebitexFormatted
import lazyStarter
import threading

l = lazyStarter.LazyStarter(True)
t = threading.Thread(target=l.main(),name=lazyMain)
t.daemon = True
t.start()