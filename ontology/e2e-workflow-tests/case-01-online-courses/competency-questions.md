# Case 01: Online Course Platform

## Domain Description

A simple online learning platform with instructors who teach courses,
courses that contain ordered modules, and students who enroll in courses.

## Ontology Patterns Tested

- 1:N relationship chains (Instructor -> Course -> Module)
- M:N relationship via junction entity (Student <-> Course via Enrollment)
- 1:N with source-side FK (Course -> CoursePlatform, FK on Course table)
- Contextualization override (Enrollment -> Course uses Enrollment table)
- Source-side contextualization (publishedOn uses Course table, not target)
- String and DateTime property types
- BigInt property type (Module.orderNum)

## Competency Questions

### CQ1: Which courses cover a given topic?

> "Which courses cover topic 'Programming'?"

Tests: Simple node property filtering (WHERE on a property value).
Expected: C001 (Intro to Python), C003 (Web Development)

### CQ2: Who teaches a given course?

> "Who teaches course 'Data Science 101'?"

Tests: Edge traversal (Instructor -> Course) with WHERE filter.
Expected: Prof. Jones

### CQ3: How many students are enrolled in each course?

> "How many students are enrolled in each course?"

Tests: Aggregation (COUNT) across edge traversals.
Expected: C001=2, C002=2, C003=1, C004=1

### CQ4: What modules belong to a given course?

> "What modules belong to course 'Intro to Python'?"

Tests: 1:N edge traversal with ORDER BY.
Expected: Variables and Types, Control Flow, Functions (ordered by orderNum)

### CQ5: Which courses does a given student take?

> "Which courses does student 'Alice' take?"

Tests: Multi-hop edge traversal (Student -> Enrollment -> Course).
Expected: Intro to Python, Data Science 101

### CQ6: Which platform hosts a given course?

> "Which platform hosts 'Intro to Python'?"

Tests: Edge traversal (Course -> CoursePlatform) via publishedOn with source-side contextualization.
Expected: Udemy

### CQ7: How many courses are published on each platform?

> "How many courses are on each platform?"

Tests: Aggregation (COUNT) across publishedOn edges grouped by platform.
Expected: Udemy=2, Coursera=1, Skillshare=1
