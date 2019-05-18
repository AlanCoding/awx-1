import json


with open('awx/alan.log') as f:
    content = f.read()

lines = content.strip().split('\n')

# print(json.dumps(lines, indent=2))

data = []

for line in lines:
    header, stuff = line.split('alan', 1)
    stuff = stuff.strip().replace('-', ' ')
    ldata = stuff.split(' ')

    times = []
    names = []
    for item in ldata:
        if item.endswith('_1') or item.endswith('_2'):
            names.append(item)
        else:
            times.append(float(item))

    start = times[0]
    for i in range(len(times)):
        times[i] -= start

    # print('names {}'.format(len(names)))
    # print(names)
    # print('times {}'.format(len(times)))
    # print(times)
    # assert len(names) == len(times)

    pts = {}
    costs = {}
    seen = set()
    costs['total'] = times[-1]
    is_request = True
    for i, name in enumerate(names):
        use_name = name[:-len('_1')]
        if (name in seen) and 'request' not in costs:
            costs['request'] = times[i] - times[i - 1]
            is_request = False

        if is_request:
            use_name = '{}_request'.format(use_name)
        pts.setdefault(use_name, [])
        pts[use_name].append(times[i])

        seen.add(name)

    # print(json.dumps(pts, indent=2))

    for name in pts.copy():
        if len(pts[name]) == 1:
            pass
        elif len(pts[name]) == 2:
            l = pts[name]
            costs[name] = l[1] - l[0]
        else:
            raise Exception('something went wrong')


    print(json.dumps(costs, indent=2))
    data.append(costs)



