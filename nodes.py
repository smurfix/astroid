# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""
on all nodes :
 .is_statement, returning true if the node should be considered as a
  statement node
 .root(), returning the root node of the tree (i.e. a Module)
 .previous_sibling(), returning previous sibling statement node
 .next_sibling(), returning next sibling statement node
 .statement(), returning the first parent node marked as statement node
 .frame(), returning the first node defining a new local scope (i.e.
  Module, Function or Class)
 .set_local(name, node), define an identifier <name> on the first parent frame,
  with the node defining it. This is used by the astng builder and should not
  be used from out there.
 .as_string(), returning a string representation of the code (should be
  executable).

on From and Import :
 .real_name(name),

 [1] http://docs.python.org/lib/module-compiler.ast.html

:author:    Sylvain Thenault
:copyright: 2003-2008 LOGILAB S.A. (Paris, FRANCE)
:contact:   http://www.logilab.fr/ -- mailto:python-projects@logilab.org
:copyright: 2003-2008 Sylvain Thenault
:contact:   mailto:thenault@gmail.com
"""

from __future__ import generators

__docformat__ = "restructuredtext en"

from itertools import imap

from logilab.astng._nodes_ast import *
try:
    from logilab.astng._nodes_ast import *
    from logilab.astng._nodes_ast import _const_factory
    AST_MODE = '_ast'
except ImportError:
    from logilab.astng._nodes_compiler import *            
    from logilab.astng._nodes_compiler import _const_factory
    AST_MODE = 'compiler'


from logilab.astng._exceptions import UnresolvableName, NotFoundError, InferenceError
from logilab.astng.utils import extend_class

INFER_NEED_NAME_STMTS = (From, Import, Global, TryExcept)

import re
ID_RGX = re.compile('^[a-zA-Z_][a-zA-Z_0-9]*$')
del re


# Node  ######################################################################

class NodeNG:
    """/!\ this class should not be used directly /!\ it's
    only used as a methods and attribute container, and update the
    original class from the compiler.ast module using its dictionnary
    (see below the class definition)
    """
    
    # attributes below are set by the builder module or by raw factories
    fromlineno = None
    tolineno = None
    # parent node in the tree
    parent = None

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, getattr(self, 'name', ''))
    
    def parent_of(self, node):
        """return true if i'm a parent of the given node"""
        parent = node.parent
        while parent is not None:
            if self is parent:
                return True
            parent = parent.parent
        return False

    def statement(self):
        """return the first parent node marked as statement node
        """
        if self.is_statement:
            return self
        return self.parent.statement()

    def frame(self):
        """return the first parent frame node (i.e. Module, Function or Class)
        """
        return self.parent.frame()

    def scope(self):
        """return the first node defining a new scope (i.e. Module,
        Function, Class, Lambda but also GenExpr)
        """
        return self.parent.scope()

    def root(self):
        """return the root node of the tree, (i.e. a Module)
        """
        if self.parent:
            return self.parent.root()
        return self

    def next_sibling(self):
        """return the previous sibling statement 
        """
        while not self.is_statement: 
            self = self.parent
        index = self.parent.nodes.index(self)
        try:
            return self.parent.nodes[index+1]
        except IndexError:
            return

    def previous_sibling(self):
        """return the next sibling statement 
        """
        while not self.is_statement: 
            self = self.parent
        index = self.parent.nodes.index(self)
        if index > 0:
            return self.parent.nodes[index-1]
        return

    def nearest(self, nodes):
        """return the node which is the nearest before this one in the
        given list of nodes
        """
        myroot = self.root()
        mylineno = self.source_line()
        nearest = None, 0
        for node in nodes:
            assert node.root() is myroot, \
                   'not from the same module %s' % (self, node)
            lineno = node.source_line()
            if node.source_line() > mylineno:
                break
            if lineno > nearest[1]:
                nearest = node, lineno
        # FIXME: raise an exception if nearest is None ?
        return nearest[0]
    
    def source_line(self):
        """return the line number where the given node appears

        we need this method since not all nodes as the lineno attribute
        correctly set...
        """
        line = self.lineno
        if line is None:
            _node = self
            try:
                while line is None:
                    _node = _node.getChildNodes()[0]
                    line = _node.lineno
            except IndexError:
                _node = self.parent
                while _node and line is None:
                    line = _node.lineno
                    _node = _node.parent
            self.lineno = line
        return line
    
    def last_source_line(self):
        """return the last block line number for this node (i.e. including
        children)
        """
        try:
            return self.__dict__['_cached_last_source_line']
        except KeyError:
            line = self.source_line()
            for node in self.getChildNodes():
                line = max(line, node.last_source_line())
            self._cached_last_source_line = line
            return line

    def block_range(self, lineno):
        """handle block line numbers range for non block opening statements
        """
        return lineno, self.last_source_line()


    def set_local(self, name, stmt):
        """delegate to a scoped parent handling a locals dictionary
        """
        self.parent.set_local(name, stmt)

    def nodes_of_class(self, klass, skip_klass=None):
        """return an iterator on nodes which are instance of the given class(es)

        klass may be a class object or a tuple of class objects
        """
        if isinstance(self, klass):
            yield self
        for child_node in self.getChildNodes():
            if skip_klass is not None and isinstance(child_node, skip_klass):
                continue
            for matching in child_node.nodes_of_class(klass, skip_klass):
                yield matching

    def _infer_name(self, frame, name):
        if isinstance(self, INFER_NEED_NAME_STMTS) or (
                 isinstance(self, (Function, Lambda)) and self is frame):
            return name
        return None

    def eq(self, value):
        return False
    
extend_class(Node, NodeNG)

Module.fromlineno = 0
Module.tolineno = 0


def const_factory(value):
    try:
        cls, value = CONST_VALUE_TRANSFORMS[value]
        node = cls(value)
    except KeyError:
        node = _const_factory(value)
    return node

# block range overrides #######################################################

def object_block_range(node, lineno):
    """handle block line numbers range for function/class statements:

    start from the "def" or "class" position whatever the given lineno
    """
    return node.source_line(), node.last_source_line()

Function.block_range = object_block_range
Class.block_range = object_block_range
Module.block_range = object_block_range

def if_block_range(node, lineno):
    """handle block line numbers range for if/elif statements
    """
    last = None
    for test, testbody in node.tests[1:]:
        if lineno == testbody.source_line():
            return lineno, lineno
        if lineno <= testbody.last_source_line():
            return lineno, testbody.last_source_line()
        if last is None:
            last = testbody.source_line() - 1
    return elsed_block_range(node, lineno, last)

If.block_range = if_block_range

def try_except_block_range(node, lineno):
    """handle block line numbers range for try/except statements
    """
    last = None
    for excls, exinst, exbody in node.handlers:
        if excls and lineno == excls.source_line():
            return lineno, lineno
        if exbody.source_line() <= lineno <= exbody.last_source_line():
            return lineno, exbody.last_source_line()
        if last is None:
            last = exbody.source_line() - 1
    return elsed_block_range(node, lineno, last)

TryExcept.block_range = try_except_block_range

def elsed_block_range(node, lineno, last=None):
    """handle block line numbers range for try/finally, for and while
    statements
    """
    if lineno == node.source_line():
        return lineno, lineno
    if node.else_:
        if lineno >= node.else_.source_line():
            return lineno, node.else_.last_source_line()
        return lineno, node.else_.source_line() - 1
    return lineno, last or node.last_source_line()

TryFinally.block_range = elsed_block_range
While.block_range = elsed_block_range
For.block_range = elsed_block_range

# From and Import #############################################################

def real_name(node, asname):
    """get name from 'as' name
    """
    for index in range(len(node.names)):
        name, _asname = node.names[index]
        if name == '*':
            return asname
        if not _asname:
            name = name.split('.', 1)[0]
            _asname = name
        if asname == _asname:
            return name
    raise NotFoundError(asname)
    
From.real_name = real_name
Import.real_name = real_name

def infer_name_module(node, name):
    context = InferenceContext(node)
    context.lookupname = name
    return node.infer(context, asname=False)
Import.infer_name_module = infer_name_module

# as_string ###################################################################

def add_as_string(node):
    """return an ast.Add node as string"""
    return '(%s) + (%s)' % (node.left.as_string(), node.right.as_string())
Add.as_string = add_as_string

def and_as_string(node):
    """return an ast.And node as string"""
    return ' and '.join(['(%s)' % n.as_string() for n in node.nodes])
And.as_string = and_as_string
    
def assert_as_string(node):
    """return an ast.Assert node as string"""
    if node.fail:
        return 'assert %s, %s' % (node.test.as_string(), node.fail.as_string())
    return 'assert %s' % node.test.as_string()
Assert.as_string = assert_as_string

def assign_as_string(node):
    """return an ast.Assign node as string"""
    lhs = ' = '.join([n.as_string() for n in node.nodes])
    return '%s = %s' % (lhs, node.expr.as_string())
Assign.as_string = assign_as_string

def augassign_as_string(node):
    """return an ast.AugAssign node as string"""
    return '%s %s %s' % (node.node.as_string(), node.op, node.expr.as_string())
AugAssign.as_string = augassign_as_string

def backquote_as_string(node):
    """return an ast.Backquote node as string"""
    return '`%s`' % node.expr.as_string()
Backquote.as_string = backquote_as_string

def bitand_as_string(node):
    """return an ast.Bitand node as string"""
    return ' & '.join(['(%s)' % n.as_string() for n in node.nodes])
Bitand.as_string = bitand_as_string

def bitor_as_string(node):
    """return an ast.Bitor node as string"""
    return ' | '.join(['(%s)' % n.as_string() for n in node.nodes])
Bitor.as_string = bitor_as_string

def bitxor_as_string(node):
    """return an ast.Bitxor node as string"""
    return ' ^ '.join(['(%s)' % n.as_string() for n in node.nodes])
Bitxor.as_string = bitxor_as_string

def break_as_string(node):
    """return an ast.Break node as string"""
    return 'break'
Break.as_string = break_as_string

def callfunc_as_string(node):
    """return an ast.CallFunc node as string"""
    expr_str = node.node.as_string()
    args = ', '.join([arg.as_string() for arg in node.args])
    if node.star_args:
        args += ', *%s' % node.star_args.as_string()
    if node.dstar_args:
        args += ', **%s' % node.dstar_args.as_string()
    return '%s(%s)' % (expr_str, args)
CallFunc.as_string = callfunc_as_string

def class_as_string(node):
    """return an ast.Class node as string"""
    bases =  ', '.join([n.as_string() for n in node.bases])
    bases = bases and '(%s)' % bases or ''
    docs = node.doc and '\n    """%s"""' % node.doc or ''
    return 'class %s%s:%s\n    %s\n' % (node.name, bases, docs,
                                        node.code.as_string())
Class.as_string = class_as_string

def compare_as_string(node):
    """return an ast.Compare node as string"""
    rhs_str = ' '.join(['%s %s' % (op, expr.as_string())
                        for op, expr in node.ops])
    return '%s %s' % (node.expr.as_string(), rhs_str)
Compare.as_string = compare_as_string

def continue_as_string(node):
    """return an ast.Continue node as string"""
    return 'continue'
Continue.as_string = continue_as_string

def dict_as_string(node):
    """return an ast.Dict node as string"""
    return '{%s}' % ', '.join(['%s: %s' % (key.as_string(), value.as_string())
                               for key, value in node.items])
Dict.as_string = dict_as_string

def div_as_string(node):
    """return an ast.Div node as string"""
    return '(%s) / (%s)' % (node.left.as_string(), node.right.as_string())
Div.as_string = div_as_string

def floordiv_as_string(node):
    """return an ast.Div node as string"""
    return '(%s) // (%s)' % (node.left.as_string(), node.right.as_string())
FloorDiv.as_string = floordiv_as_string

def ellipsis_as_string(node):
    """return an ast.Ellipsis node as string"""
    return '...'
Ellipsis.as_string = ellipsis_as_string

def exec_as_string(node):
    """return an ast.Exec node as string"""
    if node.globals:
        return 'exec %s in %s, %s' % (node.expr.as_string(),
                                      node.locals.as_string(),
                                      node.globals.as_string())
    if node.locals:
        return 'exec %s in %s' % (node.expr.as_string(),
                                  node.locals.as_string())
    return 'exec %s' % node.expr.as_string()
Exec.as_string = exec_as_string

def for_as_string(node):
    """return an ast.For node as string"""
    fors = 'for %s in %s:\n    %s' % (node.assign.as_string(),
                                      node.list.as_string(),
                                      node.body.as_string())
    if node.else_:
        fors = '%s\nelse:\n    %s' % (fors, node.else_.as_string())
    return fors
For.as_string = for_as_string

def from_as_string(node):
    """return an ast.From node as string"""
    # XXX level
    return 'from %s import %s' % (node.modname, _import_string(node.names))
From.as_string = from_as_string

def function_as_string(node):
    """return an ast.Function node as string"""
    fargs = node.format_args()
    docs = node.doc and '\n    """%s"""' % node.doc or ''
    return 'def %s(%s):%s\n    %s' % (node.name, fargs, docs,
                                      node.code.as_string())
Function.as_string = function_as_string

def genexpr_as_string(node):
    """return an ast.GenExpr node as string"""
    return '(%s)' % node.code.as_string()
GenExpr.as_string = genexpr_as_string

def global_as_string(node):
    """return an ast.Global node as string"""
    return 'global %s' % ', '.join(node.names)
Global.as_string = global_as_string

def if_as_string(node):
    """return an ast.If node as string"""
    cond, body = node.tests[0]
    ifs = ['if %s:\n    %s' % (cond.as_string(), body.as_string())]
    for cond, body in node.tests[1:]:
        ifs.append('elif %s:\n    %s' % (cond.as_string(), body.as_string()))
    if node.else_:
        ifs.append('else:\n    %s' % node.else_.as_string())
    return '\n'.join(ifs)
If.as_string = if_as_string

def import_as_string(node):
    """return an ast.Import node as string"""
    return 'import %s' % _import_string(node.names)
Import.as_string = import_as_string

def invert_as_string(node):
    """return an ast.Invert node as string"""
    return '~%s' % node.expr.as_string()
Invert.as_string = invert_as_string

def lambda_as_string(node):
    """return an ast.Lambda node as string"""
    return 'lambda %s: %s' % (node.format_args(), node.code.as_string())
Lambda.as_string = lambda_as_string

def leftshift_as_string(node):
    """return an ast.LeftShift node as string"""
    return '(%s) << (%s)' % (node.left.as_string(), node.right.as_string())
LeftShift.as_string = leftshift_as_string

def list_as_string(node):
    """return an ast.List node as string"""
    return '[%s]' % ', '.join([child.as_string() for child in node.nodes])
List.as_string = list_as_string

def listcomp_as_string(node):
    """return an ast.ListComp node as string"""
    return '[%s %s]' % (node.expr.as_string(), ' '.join([n.as_string()
                                                         for n in node.quals]))
ListComp.as_string = listcomp_as_string

def mod_as_string(node):
    """return an ast.Mod node as string"""
    return '(%s) %% (%s)' % (node.left.as_string(), node.right.as_string())
Mod.as_string = mod_as_string

def module_as_string(node):
    """return an ast.Module node as string"""
    docs = node.doc and '"""%s"""\n' % node.doc or ''
    return '%s%s' % (docs, node.node.as_string())
Module.as_string = module_as_string

def mul_as_string(node):
    """return an ast.Mul node as string"""
    return '(%s) * (%s)' % (node.left.as_string(), node.right.as_string())
Mul.as_string = mul_as_string

def name_as_string(node):
    """return an ast.Name node as string"""
    return node.name
Name.as_string = name_as_string

def not_as_string(node):
    """return an ast.Not node as string"""
    return 'not %s' % node.expr.as_string()
Not.as_string = not_as_string

def or_as_string(node):
    """return an ast.Or node as string"""
    return ' or '.join(['(%s)' % n.as_string() for n in node.nodes])
Or.as_string = or_as_string

def pass_as_string(node):
    """return an ast.Pass node as string"""
    return 'pass'
Pass.as_string = pass_as_string

def power_as_string(node):
    """return an ast.Power node as string"""
    return '(%s) ** (%s)' % (node.left.as_string(), node.right.as_string())
Power.as_string = power_as_string

def print_as_string(node):
    """return an ast.Print node as string"""
    nodes = ', '.join([n.as_string() for n in node.nodes])
    if node.dest:
        return 'print >> %s, %s,' % (node.dest.as_string(), nodes)
    return 'print %s,' % nodes
Print.as_string = print_as_string

def raise_as_string(node):
    """return an ast.Raise node as string"""
    if node.expr1:
        if node.expr2:
            if node.expr3:
                return 'raise %s, %s, %s' % (node.expr1.as_string(),
                                             node.expr2.as_string(),
                                             node.expr3.as_string())
            return 'raise %s, %s' % (node.expr1.as_string(),
                                     node.expr2.as_string())
        return 'raise %s' % node.expr1.as_string()
    return 'raise'
Raise.as_string = raise_as_string

def return_as_string(node):
    """return an ast.Return node as string"""
    return 'return %s' % node.value.as_string()
Return.as_string = return_as_string

def rightshift_as_string(node):
    """return an ast.RightShift node as string"""
    return '(%s) >> (%s)' % (node.left.as_string(), node.right.as_string())
RightShift.as_string = rightshift_as_string

def slice_as_string(node):
    """return an ast.Slice node as string"""
    # FIXME: use flags
    lower = node.lower and node.lower.as_string() or ''
    upper = node.upper and node.upper.as_string() or ''
    return '%s[%s:%s]' % (node.expr.as_string(), lower, upper)
Slice.as_string = slice_as_string

def sub_as_string(node):
    """return an ast.Sub node as string"""
    return '(%s) - (%s)' % (node.left.as_string(), node.right.as_string())
Sub.as_string = sub_as_string

def subscript_as_string(node):
    """return an ast.Subscript node as string"""
    # FIXME: flags ?
    return '%s[%s]' % (node.expr.as_string(), ','.join([n.as_string()
                                                        for n in node.subs]))
Subscript.as_string = subscript_as_string

def tryexcept_as_string(node):
    """return an ast.TryExcept node as string"""
    trys = ['try:\n    %s' % node.body.as_string()]
    for exc_type, exc_obj, body in node.handlers:
        if exc_type:
            if exc_obj:
                excs = 'except %s, %s' % (exc_type.as_string(),
                                          exc_obj.as_string())
            else:
                excs = 'except %s' % exc_type.as_string()
        else:
            excs = 'except'
        trys.append('%s:\n    %s' % (excs, body.as_string()))
    return '\n'.join(trys)
TryExcept.as_string = tryexcept_as_string

def tryfinally_as_string(node):
    """return an ast.TryFinally node as string"""
    return 'try:\n    %s\nfinally:\n    %s' % (node.body.as_string(),
                                               node.final.as_string())
TryFinally.as_string = tryfinally_as_string

def tuple_as_string(node):
    """return an ast.Tuple node as string"""
    return '(%s)' % ', '.join([child.as_string() for child in node.nodes])
Tuple.as_string = tuple_as_string

def unaryadd_as_string(node):
    """return an ast.UnaryAdd node as string"""
    return '+%s' % node.expr.as_string()
UnaryAdd.as_string = unaryadd_as_string

def unarysub_as_string(node):
    """return an ast.UnarySub node as string"""
    return '-%s' % node.expr.as_string()
UnarySub.as_string = unarysub_as_string

def while_as_string(node):
    """return an ast.While node as string"""
    whiles = 'while %s:\n    %s' % (node.test.as_string(),
                                    node.body.as_string())
    if node.else_:
        whiles = '%s\nelse:\n    %s' % (whiles, node.else_.as_string())
    return whiles
While.as_string = while_as_string

def with_as_string(node):
    """return an ast.With node as string"""
    withs = 'with (%s) as (%s):\n    %s' % (node.expr.as_string(),
                                      node.vars.as_string(),
                                      node.body.as_string())
    return withs
With.as_string = with_as_string

def yield_as_string(node):
    """yield an ast.Yield node as string"""
    return 'yield %s' % node.value.as_string()
Yield.as_string = yield_as_string


def _import_string(names):
    """return a list of (name, asname) formatted as a string
    """
    _names = []
    for name, asname in names:
        if asname is not None:
            _names.append('%s as %s' % (name, asname))
        else:
            _names.append(name)
    return  ', '.join(_names)


# special inference objects ###################################################

class Yes(object):
    """a yes object"""
    def __repr__(self):
        return 'YES'
    def __getattribute__(self, name):
        return self
    def __call__(self, *args, **kwargs):
        return self

YES = Yes()

class Proxy(object):
    """a simple proxy object"""
    def __init__(self, proxied=None):
        self._proxied = proxied

    def __getattr__(self, name):
        if name == '_proxied':
            return getattr(self.__class__, '_proxied')
        #assert self._proxied is not self
        #assert getattr(self._proxied, name) is not self
        return getattr(self._proxied, name)

    def infer(self, context=None):
        yield self


class InstanceMethod(Proxy):
    """a special node representing a function bound to an instance"""
    def __repr__(self):
        instance = self._proxied.parent.frame()
        return 'Bound method %s of %s.%s' % (self._proxied.name,
                                             instance.root().name,
                                             instance.name)
    __str__ = __repr__

    def is_bound(self):
        return True


class Instance(Proxy):
    """a special node representing a class instance"""
    def getattr(self, name, context=None, lookupclass=True):
        try:
            return self._proxied.instance_attr(name, context)
        except NotFoundError:
            if name == '__class__':
                return [self._proxied]
            if name == '__name__':
                # access to __name__ gives undefined member on class
                # instances but not on class objects
                raise NotFoundError(name)
            if lookupclass:
                return self._proxied.getattr(name, context)
        raise NotFoundError(name)

    def igetattr(self, name, context=None):
        """infered getattr"""
        try:
            # XXX frame should be self._proxied, or not ?
            return _infer_stmts(
                self._wrap_attr(self.getattr(name, context, lookupclass=False)),
                                context, frame=self)
        except NotFoundError:
            try:
                # fallback to class'igetattr since it has some logic to handle
                # descriptors
                return self._wrap_attr(self._proxied.igetattr(name, context))
            except NotFoundError:
                raise InferenceError(name)
            
    def _wrap_attr(self, attrs):
        """wrap bound methods of attrs in a InstanceMethod proxies"""
        # Guess which attrs are used in inference.
        def wrap(attr):
            if isinstance(attr, Function) and attr.type == 'method':
                return InstanceMethod(attr)
            else:
                return attr
        return imap(wrap, attrs)
        
    def infer_call_result(self, caller, context=None):
        """infer what's a class instance is returning when called"""
        infered = False
        for node in self._proxied.igetattr('__call__', context):
            for res in node.infer_call_result(caller, context):
                infered = True
                yield res
        if not infered:
            raise InferenceError()

    def __repr__(self):
        print self.__class__, self._proxied
        return 'Instance of %s.%s' % (self._proxied.root().name,
                                      self._proxied.name)
    __str__ = __repr__
    
    def callable(self):
        try:
            self._proxied.getattr('__call__')
            return True
        except NotFoundError:
            return False

    def pytype(self):
        return self._proxied.qname()
    
class Generator(Proxy): 
    """a special node representing a generator"""
    def callable(self):
        return True
    
    def pytype(self):
        return '__builtin__.generator'

# additional nodes  ##########################################################

class NoneType(Instance, NodeNG):
    """None value (instead of Name('None')"""
    _proxied_class = None.__class__
    _proxied = None
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return 'None'
    def getChildNodes(self):
        return ()
    __str__ = as_string = __repr__
    
class Bool(Instance, NodeNG):
    """None value (instead of Name('True') / Name('False')"""
    _proxied_class = bool
    _proxied = None
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return str(self.value)
    def getChildNodes(self):
        return ()
    __str__ = as_string = __repr__

CONST_NAME_TRANSFORMS = {'None': (NoneType, None),
                         'True': (Bool, True),
                         'False': (Bool, False)}
CONST_VALUE_TRANSFORMS = {None: (NoneType, None),
                          True: (Bool, True),
                          False: (Bool, False)}


# inference utilities #########################################################

class InferenceContext(object):
    __slots__ = ('startingfrom', 'path', 'lookupname', 'callcontext', 'boundnode')
    
    def __init__(self, node=None, path=None):
        self.startingfrom = node # XXX useful ?
        if path is None:
            self.path = []
        else:
            self.path = path
        self.lookupname = None
        self.callcontext = None
        self.boundnode = None

    def push(self, node):
        name = self.lookupname
        if (node, name) in self.path:
            raise StopIteration()
        self.path.append( (node, name) )

    def pop(self):
        return self.path.pop()

    def clone(self):
        # XXX copy lookupname/callcontext ?
        clone = InferenceContext(self.startingfrom, self.path)
        clone.callcontext = self.callcontext
        clone.boundnode = self.boundnode
        return clone

def _infer_stmts(stmts, context, frame=None):
    """return an iterator on statements infered by each statement in <stmts>
    """
    stmt = None
    infered = False
    if context is not None:
        name = context.lookupname
        context = context.clone()
    else:
        name = None
        context = InferenceContext()
    for stmt in stmts:
        if stmt is YES:
            yield stmt
            infered = True
            continue
        context.lookupname = stmt._infer_name(frame, name)
        try:
            for infered in stmt.infer(context):
                yield infered
                infered = True
        except UnresolvableName:
            continue
        except InferenceError:
            yield YES
            infered = True
    if not infered:
        raise InferenceError(str(stmt))

def infer_end(self, context=None):
    """inference's end for node such as Module, Class, Function, Const...
    """
    yield self

def end_ass_type(self):
    return self

