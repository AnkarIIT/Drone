"""skybrain - the detection, tracking and decision core of a counter-drone system.

Working name. Pipeline: sensors -> tracker -> classifier -> threat assessment -> ROE engine -> audit log.
No effector (jam / intercept) code lives here by design: responses are only *recommended*
to a human operator, and any real effector must be an authorised third-party adapter.
"""
