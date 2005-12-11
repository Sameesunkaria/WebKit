// -*- c-basic-offset: 2 -*-
/*
 *  This file is part of the KDE libraries
 *  Copyright (C) 1999-2000 Harri Porten (porten@kde.org)
 *  Copyright (C) 2001 Peter Kelly (pmk@post.com)
 *  Copyright (C) 2003 Apple Computer, Inc.
 *
 *  This library is free software; you can redistribute it and/or
 *  modify it under the terms of the GNU Library General Public
 *  License as published by the Free Software Foundation; either
 *  version 2 of the License, or (at your option) any later version.
 *
 *  This library is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 *  Library General Public License for more details.
 *
 *  You should have received a copy of the GNU Library General Public License
 *  along with this library; see the file COPYING.LIB.  If not, write to
 *  the Free Software Foundation, Inc., 51 Franklin Steet, Fifth Floor,
 *  Boston, MA 02110-1301, USA.
 *
 */

#ifndef _NODES_H_
#define _NODES_H_

#include <kxmlcore/RefPtr.h>

#include "internal.h"

namespace KJS {

  class ProgramNode;
  class PropertyNode;
  class PropertyValueNode;
  class Reference;
  class RegExp;
  class SourceElementsNode;
  class SourceStream;

  enum Operator { OpEqual,
		  OpEqEq,
		  OpNotEq,
		  OpStrEq,
		  OpStrNEq,
		  OpPlusEq,
		  OpMinusEq,
		  OpMultEq,
		  OpDivEq,
                  OpPlusPlus,
		  OpMinusMinus,
		  OpLess,
		  OpLessEq,
		  OpGreater,
		  OpGreaterEq,
		  OpAndEq,
		  OpXOrEq,
		  OpOrEq,
		  OpModEq,
                  OpAnd,
                  OpOr,
		  OpBitAnd,
		  OpBitXOr,
		  OpBitOr,
		  OpLShift,
		  OpRShift,
		  OpURShift,
		  OpIn,
		  OpInstanceOf
  };

  class Node {
  public:
    Node();
    virtual ~Node();

    virtual JSValue *evaluate(ExecState *exec) = 0;
    UString toString() const;
    virtual void streamTo(SourceStream &s) const = 0;
    virtual void processVarDecls(ExecState *) {}
    int lineNo() const { return line; }

    // reference counting mechanism
    void ref() { ++m_refcount; }
    void deref() { --m_refcount; if (!m_refcount) delete this; }
    unsigned int refcount() { return m_refcount; }

    virtual Node *nodeInsideAllParens();

    virtual bool isLocation() const { return false; }
    virtual bool isResolveNode() const { return false; }
    virtual bool isBracketAccessorNode() const { return false; }
    virtual bool isDotAccessorNode() const { return false; }
    virtual bool isGroupNode() const { return false; }

  protected:
    Completion createErrorCompletion(ExecState *, ErrorType, const char *msg);
    Completion createErrorCompletion(ExecState *, ErrorType, const char *msg, const Identifier &);

    JSValue *throwError(ExecState *, ErrorType, const char *msg);
    JSValue *throwError(ExecState *, ErrorType, const char *msg, JSValue *, Node *);
    JSValue *throwError(ExecState *, ErrorType, const char *msg, const Identifier &);
    JSValue *throwError(ExecState *, ErrorType, const char *msg, JSValue *, const Identifier &);
    JSValue *throwError(ExecState *, ErrorType, const char *msg, JSValue *, Node *, Node *);
    JSValue *throwError(ExecState *, ErrorType, const char *msg, JSValue *, Node *, const Identifier &);

    JSValue *throwUndefinedVariableError(ExecState *, const Identifier &);

    void setExceptionDetailsIfNeeded(ExecState *);

    int line;
    UString sourceURL;
    unsigned int m_refcount;
    virtual int sourceId() const { return -1; }

  private:
    // disallow assignment
    Node& operator=(const Node&);
    Node(const Node &other);
  };

  class StatementNode : public Node {
  public:
    StatementNode();
    void setLoc(int line0, int line1, int sourceId);
    int firstLine() const { return l0; }
    int lastLine() const { return l1; }
    int sourceId() const { return sid; }
    bool hitStatement(ExecState *exec);
    virtual Completion execute(ExecState *exec) = 0;
    void pushLabel(const Identifier &id) { ls.push(id); }
    virtual void processFuncDecl(ExecState *exec);
  protected:
    LabelStack ls;
  private:
    JSValue *evaluate(ExecState */*exec*/) { return jsUndefined(); }
    int l0, l1;
    int sid;
    bool breakPoint;
  };

  class NullNode : public Node {
  public:
    NullNode() {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  };

  class BooleanNode : public Node {
  public:
    BooleanNode(bool v) : value(v) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    bool value;
  };

  class NumberNode : public Node {
  public:
    NumberNode(double v) : value(v) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    double value;
  };

  class StringNode : public Node {
  public:
    StringNode(const UString *v) { value = *v; }
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    UString value;
  };

  class RegExpNode : public Node {
  public:
    RegExpNode(const UString &p, const UString &f)
      : pattern(p), flags(f) { }
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    UString pattern, flags;
  };

  class ThisNode : public Node {
  public:
    ThisNode() {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  };

  class ResolveNode : public Node {
  public:
    ResolveNode(const Identifier &s) : ident(s) { }
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;

    virtual bool isLocation() const { return true; }
    virtual bool isResolveNode() const { return true; }
    const Identifier& identifier() const { return ident; }

  private:
    Identifier ident;
  };

  class GroupNode : public Node {
  public:
    GroupNode(Node *g) : group(g) { }
    virtual JSValue *evaluate(ExecState *exec);
    virtual Node *nodeInsideAllParens();
    virtual void streamTo(SourceStream &s) const;
    virtual bool isGroupNode() const { return true; }
  private:
    RefPtr<Node> group;
  };

  class ElementNode : public Node {
  public:
    // list pointer is tail of a circular list, cracked in the ArrayNode ctor
    ElementNode(int e, Node *n) : list(this), elision(e), node(n) { }
    ElementNode(ElementNode *l, int e, Node *n)
      : list(l->list), elision(e), node(n) { l->list = this; }
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    friend class ArrayNode;
    RefPtr<ElementNode> list;
    int elision;
    RefPtr<Node> node;
  };

  class ArrayNode : public Node {
  public:
    ArrayNode(int e) : element(0), elision(e), opt(true) { }
    ArrayNode(ElementNode *ele)
      : element(ele->list), elision(0), opt(false) { ele->list = 0; }
    ArrayNode(int eli, ElementNode *ele)
      : element(ele->list), elision(eli), opt(true) { ele->list = 0; }
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<ElementNode> element;
    int elision;
    bool opt;
  };

  class PropertyValueNode : public Node {
  public:
    // list pointer is tail of a circular list, cracked in the ObjectLiteralNode ctor
    PropertyValueNode(PropertyNode *n, Node *a)
      : name(n), assign(a), list(this) { }
    PropertyValueNode(PropertyNode *n, Node *a, PropertyValueNode *l)
      : name(n), assign(a), list(l->list) { l->list = this; }
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    friend class ObjectLiteralNode;
    RefPtr<PropertyNode> name;
    RefPtr<Node> assign;
    RefPtr<PropertyValueNode> list;
  };

  class ObjectLiteralNode : public Node {
  public:
    ObjectLiteralNode() : list(0) { }
    ObjectLiteralNode(PropertyValueNode *l) : list(l->list) { l->list = 0; }
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<PropertyValueNode> list;
  };

  class PropertyNode : public Node {
  public:
    PropertyNode(double d) : numeric(d) { }
    PropertyNode(const Identifier &s) : str(s) { }
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    double numeric;
    Identifier str;
  };

  class BracketAccessorNode : public Node {
  public:
    BracketAccessorNode(Node *e1, Node *e2) : expr1(e1), expr2(e2) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;

    virtual bool isLocation() const { return true; }
    virtual bool isBracketAccessorNode() const { return true; }
    Node *base() { return expr1.get(); }
    Node *subscript() { return expr2.get(); }

  private:
    RefPtr<Node> expr1;
    RefPtr<Node> expr2;
  };

  class DotAccessorNode : public Node {
  public:
    DotAccessorNode(Node *e, const Identifier &s) : expr(e), ident(s) { }
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;

    virtual bool isLocation() const { return true; }
    virtual bool isDotAccessorNode() const { return true; }
    Node *base() const { return expr.get(); }
    const Identifier& identifier() const { return ident; }

  private:
    RefPtr<Node> expr;
    Identifier ident;
  };

  class ArgumentListNode : public Node {
  public:
    // list pointer is tail of a circular list, cracked in the ArgumentsNode ctor
    ArgumentListNode(Node *e) : list(this), expr(e) { }
    ArgumentListNode(ArgumentListNode *l, Node *e)
      : list(l->list), expr(e) { l->list = this; }
    JSValue *evaluate(ExecState *exec);
    List evaluateList(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    friend class ArgumentsNode;
    RefPtr<ArgumentListNode> list;
    RefPtr<Node> expr;
  };

  class ArgumentsNode : public Node {
  public:
    ArgumentsNode() : list(0) { }
    ArgumentsNode(ArgumentListNode *l)
      : list(l->list) { l->list = 0; }
    JSValue *evaluate(ExecState *exec);
    List evaluateList(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<ArgumentListNode> list;
  };

  class NewExprNode : public Node {
  public:
    NewExprNode(Node *e) : expr(e), args(0) {}
    NewExprNode(Node *e, ArgumentsNode *a) : expr(e), args(a) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
    RefPtr<ArgumentsNode> args;
  };

  class FunctionCallValueNode : public Node {
  public:
    FunctionCallValueNode(Node *e, ArgumentsNode *a) : expr(e), args(a) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
    RefPtr<ArgumentsNode> args;
  };

  class FunctionCallResolveNode : public Node {
  public:
    FunctionCallResolveNode(const Identifier& i, ArgumentsNode *a) : ident(i), args(a) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    Identifier ident;
    RefPtr<ArgumentsNode> args;
  };

  class FunctionCallBracketNode : public Node {
  public:
    FunctionCallBracketNode(Node *b, Node *s, ArgumentsNode *a) : base(b), subscript(s), args(a) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  protected:
    RefPtr<Node> base;
    RefPtr<Node> subscript;
    RefPtr<ArgumentsNode> args;
  };

  class FunctionCallParenBracketNode : public FunctionCallBracketNode {
  public:
    FunctionCallParenBracketNode(Node *b, Node *s, ArgumentsNode *a) : FunctionCallBracketNode(b, s, a) {}
    virtual void streamTo(SourceStream &s) const;
  };

  class FunctionCallDotNode : public Node {
  public:
    FunctionCallDotNode(Node *b, const Identifier &i, ArgumentsNode *a) : base(b), ident(i), args(a) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  protected:
    RefPtr<Node> base;
    Identifier ident;
    RefPtr<ArgumentsNode> args;
  };

  class FunctionCallParenDotNode : public FunctionCallDotNode {
  public:
    FunctionCallParenDotNode(Node *b, const Identifier &i, ArgumentsNode *a) : FunctionCallDotNode(b, i, a) {}
    virtual void streamTo(SourceStream &s) const;
  };

  class PostfixResolveNode : public Node {
  public:
    PostfixResolveNode(const Identifier& i, Operator o) : m_ident(i), m_oper(o) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    Identifier m_ident;
    Operator m_oper;
  };

  class PostfixBracketNode : public Node {
  public:
    PostfixBracketNode(Node *b, Node *s, Operator o) : m_base(b), m_subscript(s), m_oper(o) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> m_base;
    RefPtr<Node> m_subscript;
    Operator m_oper;
  };

  class PostfixDotNode : public Node {
  public:
    PostfixDotNode(Node *b, const Identifier& i, Operator o) : m_base(b), m_ident(i), m_oper(o) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> m_base;
    Identifier m_ident;
    Operator m_oper;
  };

  class DeleteResolveNode : public Node {
  public:
    DeleteResolveNode(const Identifier& i) : m_ident(i) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    Identifier m_ident;
  };

  class DeleteBracketNode : public Node {
  public:
    DeleteBracketNode(Node *base, Node *subscript) : m_base(base), m_subscript(subscript) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> m_base;
    RefPtr<Node> m_subscript;
  };

  class DeleteDotNode : public Node {
  public:
    DeleteDotNode(Node *base, const Identifier& i) : m_base(base), m_ident(i) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> m_base;
    Identifier m_ident;
  };

  class DeleteValueNode : public Node {
  public:
    DeleteValueNode(Node *e) : m_expr(e) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> m_expr;
  };

  class VoidNode : public Node {
  public:
    VoidNode(Node *e) : expr(e) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
  };

  class TypeOfResolveNode : public Node {
  public:
    TypeOfResolveNode(const Identifier& i) : m_ident(i) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    Identifier m_ident;
  };

  class TypeOfValueNode : public Node {
  public:
    TypeOfValueNode(Node *e) : m_expr(e) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> m_expr;
  };

  class PrefixResolveNode : public Node {
  public:
    PrefixResolveNode(const Identifier& i, Operator o) : m_ident(i), m_oper(o) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    Identifier m_ident;
    Operator m_oper;
  };

  class PrefixBracketNode : public Node {
  public:
    PrefixBracketNode(Node *b, Node *s, Operator o) : m_base(b), m_subscript(s), m_oper(o) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> m_base;
    RefPtr<Node> m_subscript;
    Operator m_oper;
  };

  class PrefixDotNode : public Node {
  public:
    PrefixDotNode(Node *b, const Identifier& i, Operator o) : m_base(b), m_ident(i), m_oper(o) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> m_base;
    Identifier m_ident;
    Operator m_oper;
  };

  class UnaryPlusNode : public Node {
  public:
    UnaryPlusNode(Node *e) : expr(e) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
  };

  class NegateNode : public Node {
  public:
    NegateNode(Node *e) : expr(e) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
  };

  class BitwiseNotNode : public Node {
  public:
    BitwiseNotNode(Node *e) : expr(e) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
  };

  class LogicalNotNode : public Node {
  public:
    LogicalNotNode(Node *e) : expr(e) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
  };

  class MultNode : public Node {
  public:
    MultNode(Node *t1, Node *t2, char op) : term1(t1), term2(t2), oper(op) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> term1;
    RefPtr<Node> term2;
    char oper;
  };

  class AddNode : public Node {
  public:
    AddNode(Node *t1, Node *t2, char op) : term1(t1), term2(t2), oper(op) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> term1;
    RefPtr<Node> term2;
    char oper;
  };

  class ShiftNode : public Node {
  public:
    ShiftNode(Node *t1, Operator o, Node *t2)
      : term1(t1), term2(t2), oper(o) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> term1;
    RefPtr<Node> term2;
    Operator oper;
  };

  class RelationalNode : public Node {
  public:
    RelationalNode(Node *e1, Operator o, Node *e2) :
      expr1(e1), expr2(e2), oper(o) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr1;
    RefPtr<Node> expr2;
    Operator oper;
  };

  class EqualNode : public Node {
  public:
    EqualNode(Node *e1, Operator o, Node *e2)
      : expr1(e1), expr2(e2), oper(o) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr1;
    RefPtr<Node> expr2;
    Operator oper;
  };

  class BitOperNode : public Node {
  public:
    BitOperNode(Node *e1, Operator o, Node *e2) :
      expr1(e1), expr2(e2), oper(o) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr1;
    RefPtr<Node> expr2;
    Operator oper;
  };

  /**
   * expr1 && expr2, expr1 || expr2
   */
  class BinaryLogicalNode : public Node {
  public:
    BinaryLogicalNode(Node *e1, Operator o, Node *e2) :
      expr1(e1), expr2(e2), oper(o) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr1;
    RefPtr<Node> expr2;
    Operator oper;
  };

  /**
   * The ternary operator, "logical ? expr1 : expr2"
   */
  class ConditionalNode : public Node {
  public:
    ConditionalNode(Node *l, Node *e1, Node *e2) :
      logical(l), expr1(e1), expr2(e2) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> logical;
    RefPtr<Node> expr1;
    RefPtr<Node> expr2;
  };

  class AssignResolveNode : public Node {
  public:
    AssignResolveNode(const Identifier &ident, Operator oper, Node *right) 
      : m_ident(ident), m_oper(oper), m_right(right) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  protected:
    Identifier m_ident;
    Operator m_oper;
    RefPtr<Node> m_right;
  };

  class AssignBracketNode : public Node {
  public:
    AssignBracketNode(Node *base, Node *subscript, Operator oper, Node *right) 
      : m_base(base), m_subscript(subscript), m_oper(oper), m_right(right) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  protected:
    RefPtr<Node> m_base;
    RefPtr<Node> m_subscript;
    Operator m_oper;
    RefPtr<Node> m_right;
  };

  class AssignDotNode : public Node {
  public:
    AssignDotNode(Node *base, const Identifier& ident, Operator oper, Node *right)
      : m_base(base), m_ident(ident), m_oper(oper), m_right(right) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  protected:
    RefPtr<Node> m_base;
    Identifier m_ident;
    Operator m_oper;
    RefPtr<Node> m_right;
  };

  class CommaNode : public Node {
  public:
    CommaNode(Node *e1, Node *e2) : expr1(e1), expr2(e2) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr1;
    RefPtr<Node> expr2;
  };

  class StatListNode : public StatementNode {
  public:
    // list pointer is tail of a circular list, cracked in the CaseClauseNode ctor
    StatListNode(StatementNode *s);
    StatListNode(StatListNode *l, StatementNode *s);
    virtual Completion execute(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    friend class CaseClauseNode;
    RefPtr<StatementNode> statement;
    RefPtr<StatListNode> list;
  };

  class AssignExprNode : public Node {
  public:
    AssignExprNode(Node *e) : expr(e) {}
    JSValue *evaluate(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
  };

  class VarDeclNode : public Node {
  public:
    enum Type { Variable, Constant };
    VarDeclNode(const Identifier &id, AssignExprNode *in, Type t);
    JSValue *evaluate(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    Type varType;
    Identifier ident;
    RefPtr<AssignExprNode> init;
  };

  class VarDeclListNode : public Node {
  public:
    // list pointer is tail of a circular list, cracked in the ForNode/VarStatementNode ctor
    VarDeclListNode(VarDeclNode *v) : list(this), var(v) {}
    VarDeclListNode(VarDeclListNode *l, VarDeclNode *v)
      : list(l->list), var(v) { l->list = this; }
    JSValue *evaluate(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    friend class ForNode;
    friend class VarStatementNode;
    RefPtr<VarDeclListNode> list;
    RefPtr<VarDeclNode> var;
  };

  class VarStatementNode : public StatementNode {
  public:
    VarStatementNode(VarDeclListNode *l) : list(l->list) { l->list = 0; }
    virtual Completion execute(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<VarDeclListNode> list;
  };

  class BlockNode : public StatementNode {
  public:
    BlockNode(SourceElementsNode *s);
    virtual Completion execute(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  protected:
    RefPtr<SourceElementsNode> source;
  };

  class EmptyStatementNode : public StatementNode {
  public:
    EmptyStatementNode() { } // debug
    virtual Completion execute(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  };

  class ExprStatementNode : public StatementNode {
  public:
    ExprStatementNode(Node *e) : expr(e) { }
    virtual Completion execute(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
  };

  class IfNode : public StatementNode {
  public:
    IfNode(Node *e, StatementNode *s1, StatementNode *s2)
      : expr(e), statement1(s1), statement2(s2) {}
    virtual Completion execute(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
    RefPtr<StatementNode> statement1;
    RefPtr<StatementNode> statement2;
  };

  class DoWhileNode : public StatementNode {
  public:
    DoWhileNode(StatementNode *s, Node *e) : statement(s), expr(e) {}
    virtual Completion execute(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<StatementNode> statement;
    RefPtr<Node> expr;
  };

  class WhileNode : public StatementNode {
  public:
    WhileNode(Node *e, StatementNode *s) : expr(e), statement(s) {}
    virtual Completion execute(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
    RefPtr<StatementNode> statement;
  };

  class ForNode : public StatementNode {
  public:
    ForNode(Node *e1, Node *e2, Node *e3, StatementNode *s) :
      expr1(e1), expr2(e2), expr3(e3), statement(s) {}
    ForNode(VarDeclListNode *e1, Node *e2, Node *e3, StatementNode *s) :
      expr1(e1->list), expr2(e2), expr3(e3), statement(s) { e1->list = 0; }
    virtual Completion execute(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr1;
    RefPtr<Node> expr2;
    RefPtr<Node> expr3;
    RefPtr<StatementNode> statement;
  };

  class ForInNode : public StatementNode {
  public:
    ForInNode(Node *l, Node *e, StatementNode *s);
    ForInNode(const Identifier &i, AssignExprNode *in, Node *e, StatementNode *s);
    virtual Completion execute(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    Identifier ident;
    RefPtr<AssignExprNode> init;
    RefPtr<Node> lexpr;
    RefPtr<Node> expr;
    RefPtr<VarDeclNode> varDecl;
    RefPtr<StatementNode> statement;
  };

  class ContinueNode : public StatementNode {
  public:
    ContinueNode() { }
    ContinueNode(const Identifier &i) : ident(i) { }
    virtual Completion execute(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    Identifier ident;
  };

  class BreakNode : public StatementNode {
  public:
    BreakNode() { }
    BreakNode(const Identifier &i) : ident(i) { }
    virtual Completion execute(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    Identifier ident;
  };

  class ReturnNode : public StatementNode {
  public:
    ReturnNode(Node *v) : value(v) {}
    virtual Completion execute(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> value;
  };

  class WithNode : public StatementNode {
  public:
    WithNode(Node *e, StatementNode *s) : expr(e), statement(s) {}
    virtual Completion execute(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
    RefPtr<StatementNode> statement;
  };

  class CaseClauseNode : public Node {
  public:
    CaseClauseNode(Node *e) : expr(e), list(0) { }
    CaseClauseNode(Node *e, StatListNode *l)
      : expr(e), list(l->list) { l->list = 0; }
    JSValue *evaluate(ExecState *exec);
    Completion evalStatements(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
    RefPtr<StatListNode> list;
  };

  class ClauseListNode : public Node {
  public:
    // list pointer is tail of a circular list, cracked in the CaseBlockNode ctor
    ClauseListNode(CaseClauseNode *c) : cl(c), nx(this) { }
    ClauseListNode(ClauseListNode *n, CaseClauseNode *c)
      : cl(c), nx(n->nx) { n->nx = this; }
    JSValue *evaluate(ExecState *exec);
    CaseClauseNode *clause() const { return cl.get(); }
    ClauseListNode *next() const { return nx.get(); }
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    friend class CaseBlockNode;
    RefPtr<CaseClauseNode> cl;
    RefPtr<ClauseListNode> nx;
  };

  class CaseBlockNode : public Node {
  public:
    CaseBlockNode(ClauseListNode *l1, CaseClauseNode *d, ClauseListNode *l2);
    JSValue *evaluate(ExecState *exec);
    Completion evalBlock(ExecState *exec, JSValue *input);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<ClauseListNode> list1;
    RefPtr<CaseClauseNode> def;
    RefPtr<ClauseListNode> list2;
  };

  class SwitchNode : public StatementNode {
  public:
    SwitchNode(Node *e, CaseBlockNode *b) : expr(e), block(b) { }
    virtual Completion execute(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
    RefPtr<CaseBlockNode> block;
  };

  class LabelNode : public StatementNode {
  public:
    LabelNode(const Identifier &l, StatementNode *s) : label(l), statement(s) { }
    virtual Completion execute(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    Identifier label;
    RefPtr<StatementNode> statement;
  };

  class ThrowNode : public StatementNode {
  public:
    ThrowNode(Node *e) : expr(e) {}
    virtual Completion execute(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<Node> expr;
  };

  class TryNode : public StatementNode {
  public:
    TryNode(StatementNode *b, const Identifier &e, StatementNode *c, StatementNode *f)
      : tryBlock(b), exceptionIdent(e), catchBlock(c), finallyBlock(f) { }
    virtual Completion execute(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    RefPtr<StatementNode> tryBlock;
    Identifier exceptionIdent;
    RefPtr<StatementNode> catchBlock;
    RefPtr<StatementNode> finallyBlock;
  };

  class ParameterNode : public Node {
  public:
    // list pointer is tail of a circular list, cracked in the FuncDeclNode/FuncExprNode ctor
    ParameterNode(const Identifier &i) : id(i), next(this) { }
    ParameterNode(ParameterNode *list, const Identifier &i)
      : id(i), next(list->next) { list->next = this; }
    JSValue *evaluate(ExecState *exec);
    Identifier ident() { return id; }
    ParameterNode *nextParam() { return next.get(); }
    virtual void streamTo(SourceStream &s) const;
  private:
    friend class FuncDeclNode;
    friend class FuncExprNode;
    Identifier id;
    RefPtr<ParameterNode> next;
  };

  // inherited by ProgramNode
  class FunctionBodyNode : public BlockNode {
  public:
    FunctionBodyNode(SourceElementsNode *s);
    void processFuncDecl(ExecState *exec);
  };

  class FuncExprNode : public Node {
  public:
    FuncExprNode(const Identifier &i, FunctionBodyNode *b)
      : ident(i), param(0), body(b) { }
    FuncExprNode(const Identifier &i, ParameterNode *p, FunctionBodyNode *b)
      : ident(i), param(p->next), body(b) { p->next = 0; }
    virtual JSValue *evaluate(ExecState *);
    virtual void streamTo(SourceStream &) const;
  private:
    Identifier ident;
    RefPtr<ParameterNode> param;
    RefPtr<FunctionBodyNode> body;
  };

  class FuncDeclNode : public StatementNode {
  public:
    FuncDeclNode(const Identifier &i, FunctionBodyNode *b)
      : ident(i), param(0), body(b) { }
    FuncDeclNode(const Identifier &i, ParameterNode *p, FunctionBodyNode *b)
      : ident(i), param(p->next), body(b) { p->next = 0; }
    virtual Completion execute(ExecState *);
    virtual void processFuncDecl(ExecState *);
    virtual void streamTo(SourceStream &) const;
  private:
    Identifier ident;
    RefPtr<ParameterNode> param;
    RefPtr<FunctionBodyNode> body;
  };

  // A linked list of source element nodes
  class SourceElementsNode : public StatementNode {
  public:
    // list pointer is tail of a circular list, cracked in the BlockNode (or subclass) ctor
    SourceElementsNode(StatementNode *s1);
    SourceElementsNode(SourceElementsNode *s1, StatementNode *s2);

    Completion execute(ExecState *exec);
    void processFuncDecl(ExecState *exec);
    virtual void processVarDecls(ExecState *exec);
    virtual void streamTo(SourceStream &s) const;
  private:
    friend class BlockNode;
    RefPtr<StatementNode> element; // 'this' element
    RefPtr<SourceElementsNode> elements; // pointer to next
  };

  class ProgramNode : public FunctionBodyNode {
  public:
    ProgramNode(SourceElementsNode *s);
  };

} // namespace

#endif
