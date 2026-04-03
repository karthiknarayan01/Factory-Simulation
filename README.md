# Factory-Simulation
A multi-threaded factory floor simulation with a real-time browser dashboard. Workers run as concurrent threads sharing a synchronized buffer — part workers manufacture and deposit parts, product workers retrieve them and assemble products. Every state change is streamed live to the UI via Server-Sent Events.
