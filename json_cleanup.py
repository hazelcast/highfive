NODE_SEP = ' -> '


def visit_nodes(node):          # simple recursive tree traversal
    if hasattr(node, 'mark'):   # it's already a NodeMarker
        return node
    if hasattr(node, '__iter__') and not isinstance(node, str):
        iterator = range(len(node)) if isinstance(node, list) else node
        for thing in iterator:
            node[thing] = visit_nodes(node[thing])
    return NodeMarker(node)


# We need the roots of each node, so that we can trace our way back to the
# root from a specific node (marking nodes along the way).
# Since `visit_nodes` makes a pre-order traversal, it assigns `NodeMarker`
# to each node from inside-out, which makes it difficult to assign roots
# So, we do another traversal to store the references of the root nodes
def assign_roots(marker_node, root=None):
    node = marker_node.node
    if hasattr(node, '__iter__') and not isinstance(node, str):
        iterator = range(len(node)) if isinstance(node, list) else node
        for thing in iterator:
            assign_roots(node[thing], marker_node)
    marker_node.root = root


class NodeMarker(object):
    def __init__(self, node, root=None):
        self.root = root
        self.node = node        # actual value
        self.is_used = False    # marker

    def mark(self):
        self.is_used = True
        root = self.root
        while root and not root.is_used:
            root.is_used = True
            root = root.root

    def get_object(self, obj):
        return obj.node if hasattr(obj, 'mark') else obj

    # The following methods blindly assume that the method is supported by the
    # particular type (i.e., exceptions should be handled explicitly)

    def lower(self):
        return str(self).lower()

    # if you access the element in the usual way, then "bam!"
    def __getitem__(self, key):
        self.node[key].mark()      # it will be marked as used!
        return self.node[key]

    def get(self, key, default=None):
        if key in self.node:
            self.node[key].mark()
        return self.node.get(key, default)

    def __setitem__(self, key, val):
        self.node[key] = visit_nodes(val)

    def __hash__(self):
        return hash(self.node)

    def __iter__(self):
        return iter(self.node)

    def __eq__(self, other):
        return self.node == self.get_object(other)

    def __ne__(self, other):
        return self.node != self.get_object(other)

    def __add__(self, other):
        return self.node + self.get_object(other)

    def __mod__(self, other):
        return self.node % self.get_object(other)

    def __contains__(self, other):
        other = self.get_object(other)
        # since string is also a sequence in python, we shouldn't iterate
        # over it and check the individual characters
        if isinstance(self.node, str):
            return other in self.node

        for idx, thing in enumerate(self.node):
            if thing == other:
                if isinstance(self.node, list):
                    self.node[idx].mark()
                else:
                    self.node[thing].mark()
                return True
        return False

    def __str__(self):
        return str(self.node)

    def __int__(self):
        return int(self.node)


class JsonCleaner(object):
    def __init__(self, json_obj):
        self.unused = 0
        self.json = visit_nodes(json_obj)
        assign_roots(self.json)

    def clean(self, warn=True):
        return self.filter_nodes(self.json, warn)

    def filter_nodes(self, marker_node, warn, path=''):
        if marker_node.is_used:
            node = marker_node.node
            if hasattr(node, '__iter__') and not isinstance(node, str):
                # it's either 'list' or 'dict' when it comes to JSONs
                removed = 0
                iterator = range(len(node)) if isinstance(node, list) \
                    else node.keys()
                for thing in iterator:
                    new_path = path + str(thing) + NODE_SEP
                    # since lists maintain order, once we pop them,
                    # we decrement their indices as their length is reduced
                    if isinstance(node, list):
                        thing -= removed
                    node[thing] = self.filter_nodes(node[thing],
                                                    warn, new_path)
                    if node[thing] == ():
                        self.unused += 1
                        if warn:
                            new_path = new_path.strip(NODE_SEP)
                            print('unused node at "%s"' % new_path)
                        node.pop(thing)
                        removed += 1
            return node
        return ()
