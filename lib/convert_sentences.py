from lib.pyborg import pyborg
pb = pyborg.pyborg()
fh = open('new_seeds.txt','r')
for line in fh.readlines():
	pb.learn(pyborg.filter_message(line, pb))

pb.save_all()

