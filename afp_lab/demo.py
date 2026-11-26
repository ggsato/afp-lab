import json
from .afp import Clock, Medium, Node

def scenario(collision=False):
    clock=Clock(); radio=Medium(clock)
    a=Node(radio,1,(0,0)); b=Node(radio,2,(800,0),True); c=Node(radio,3,(1600,0))
    a.send(3,b'temperature=19.8')
    if collision: c.send(1,b'concurrent')
    clock.run()
    return dict(scenario='collision' if collision else 'relay',delivered=len(c.delivered),acked=bool(a.acked),events=radio.log)

if __name__=='__main__':
    for collision in (False,True): print(json.dumps(scenario(collision),indent=2))
