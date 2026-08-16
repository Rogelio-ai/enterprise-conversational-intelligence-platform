# 01_Restaurant_Organization.md

**Document ID:** RDM-001

**Document Name:** Restaurant Organization

**Domain Pack:** Restaurant Intelligence Platform

**Product:** Enterprise Conversational Intelligence Platform (ECIP)

**Version:** 1.0.0

**Status:** ACTIVE

**Certification Status:** APPROVED

---

# 1. PURPOSE

This document defines the canonical business structure of a restaurant organization within the Restaurant Domain Pack.

Its purpose is to model how restaurant businesses are organized independently of any specific Point of Sale (POS), ERP or operational system.

This model extends the Canonical Enterprise Intelligence Model without modifying its core entities.

---

# 2. OBJECTIVES

The Restaurant Organization Model shall enable ECIP to understand:

* Restaurant ownership.
* Corporate structure.
* Brands.
* Branches.
* Operational units.
* Departments.
* Employees.
* Customer service responsibilities.
* Business hierarchy.

The model shall support:

* Single restaurants.
* Multi-branch companies.
* Franchises.
* Restaurant groups.
* Cloud kitchens.
* Future restaurant business models.

---

# 3. RELATIONSHIP WITH THE CANONICAL MODEL

This document extends the following canonical entities:

* Organization
* Organizational Unit
* Location
* Role
* Enterprise User
* Capability Assignment

It does not replace them.

---

# 4. RESTAURANT ORGANIZATION HIERARCHY

A typical hierarchy is:

```text
Restaurant Group
        │
        ▼
Brand
        │
        ▼
Restaurant
        │
        ▼
Branch
        │
        ▼
Operational Area
        │
        ▼
Department
        │
        ▼
Workstation
```

Not every organization requires every level.

---

# 5. RESTAURANT GROUP

Represents the highest business entity that owns one or more restaurant brands.

Examples:

* Corporate holding
* Restaurant corporation
* Hospitality group

Typical attributes:

* Identifier
* Legal name
* Commercial name
* Country
* Tax identifiers
* Status
* Corporate policies

---

# 6. BRAND

Represents a commercial brand operated by a Restaurant Group.

Examples:

* Italian Restaurant Brand
* Coffee Shop Brand
* Steakhouse Brand

Typical attributes:

* Brand name
* Logo
* Brand identity
* Cuisine type
* Service model
* Default operating policies

A Restaurant Group may own multiple brands.

---

# 7. RESTAURANT

Represents one logical restaurant business.

Typical attributes:

* Restaurant identifier
* Commercial name
* Brand
* Service types
* Time zone
* Currency
* Languages
* Business hours
* Operational status

Supported service types include:

* Dine In
* Take Away
* Delivery
* Drive Through
* Catering
* Banquets
* Buffet

---

# 8. BRANCH

Represents one physical operating location.

Typical attributes:

* Branch code
* Address
* Geographic coordinates
* Contact numbers
* Opening hours
* Capacity
* Delivery zones
* Pickup availability
* Operational status

A restaurant may operate multiple branches.

---

# 9. OPERATIONAL AREAS

Each branch may contain operational areas such as:

* Dining Room
* Private Rooms
* Terrace
* Kitchen
* Bar
* Reception
* Cashier
* Pickup Area
* Delivery Dispatch
* Warehouse
* Administrative Office

Each area has:

* Capacity
* Operating hours
* Responsible manager
* Operational status

---

# 10. DEPARTMENTS

Departments represent organizational responsibilities.

Typical departments include:

* Customer Service
* Kitchen
* Bar
* Delivery
* Purchasing
* Inventory
* Maintenance
* Administration
* Finance
* Marketing

Departments are organizational concepts.

Physical areas and departments are independent.

---

# 11. WORKSTATIONS

Workstations represent operational positions where work is performed.

Examples:

* Cash Register
* Waiter Station
* Kitchen Station
* Bar Station
* Reception Desk
* Delivery Console

Typical attributes:

* Identifier
* Area
* Assigned employee
* Device
* Operational status

---

# 12. EMPLOYEE ORGANIZATION

Employees belong to organizational units.

Examples:

```text
Restaurant Manager

    ├── Dining Room Supervisor

    │       ├── Waiters

    │       └── Hosts

    │
    ├── Kitchen Supervisor

    │       ├── Grill

    │       ├── Cold Kitchen

    │       └── Desserts

    │
    ├── Bar Supervisor

    └── Delivery Supervisor
```

The hierarchy may vary by restaurant.

---

# 13. ROLES

Typical enterprise roles include:

Executive

* Owner
* Director
* Regional Manager

Management

* Restaurant Manager
* Assistant Manager

Operations

* Supervisor
* Waiter
* Host
* Cashier
* Cook
* Chef
* Bartender
* Delivery Dispatcher
* Driver

Support

* Inventory Manager
* Purchasing
* Maintenance Technician
* Accountant
* Marketing

Roles define responsibilities.

Permissions are governed independently.

---

# 14. SERVICE CHANNELS

Each branch may enable one or more channels:

* Telephone
* Walk-in
* Website
* Mobile App
* WhatsApp
* SMS
* Facebook
* Instagram
* Delivery Platforms
* Kiosk

Channel availability is configurable.

---

# 15. BUSINESS HOURS

Operating schedules may be defined for:

* Restaurant
* Branch
* Operational Area
* Service Type
* Holiday
* Special Event

The platform shall support exceptions without modifying normal schedules.

---

# 16. CAPACITY

Capacity is modeled at multiple levels.

Examples:

Restaurant Capacity

* Maximum guests

Dining Room Capacity

* Tables
* Seats

Kitchen Capacity

* Simultaneous orders

Delivery Capacity

* Active deliveries
* Driver availability

Capacity contributes to Operational Context.

---

# 17. SERVICE AVAILABILITY

Availability depends on:

* Business hours
* Capacity
* Staffing
* Inventory
* Equipment status
* Maintenance
* Special events

Availability is dynamic.

---

# 18. FRANCHISE SUPPORT

The model supports franchise organizations.

Additional concepts include:

* Franchise Owner
* Franchise Agreement
* Territory
* Franchise Policies
* Shared Brand Standards

Franchise-specific concepts extend this model.

---

# 19. CLOUD KITCHENS

The model supports cloud kitchens.

Characteristics include:

* No dining room
* Delivery only
* Multiple virtual brands
* Shared kitchen
* Shared inventory
* Shared production

Cloud kitchens remain compatible with the same enterprise model.

---

# 20. MULTI-BRAND OPERATIONS

A single physical branch may serve multiple brands.

Examples:

```text
Kitchen

├── Brand A

├── Brand B

└── Brand C
```

The organization model shall support shared resources across brands.

---

# 21. ORGANIZATIONAL EVENTS

Typical events include:

* RestaurantCreated
* BranchOpened
* BranchClosed
* BranchStatusChanged
* AreaOpened
* AreaClosed
* DepartmentCreated
* WorkstationActivated
* WorkstationDeactivated
* EmployeeAssigned
* EmployeeTransferred
* BusinessHoursChanged

These events contribute to Enterprise Context.

---

# 22. RELATIONSHIPS

Examples:

```text
RestaurantGroup
    OWNS Brand

Brand
    OPERATES Restaurant

Restaurant
    HAS Branch

Branch
    HAS OperationalArea

OperationalArea
    CONTAINS Workstation

Department
    RESPONSIBLE_FOR OperationalArea

EnterpriseUser
    ASSIGNED_TO Department

Employee
    ASSIGNED_TO Workstation
```

---

# 23. BUSINESS RULES

The following rules apply:

* Every Branch belongs to exactly one Restaurant.
* Every Restaurant belongs to one Brand.
* Every Brand belongs to one Restaurant Group.
* A Workstation belongs to one Operational Area.
* An Operational Area may contain multiple Workstations.
* Departments and Areas are independent concepts.
* Service availability shall consider operational capacity.
* Organizational changes shall preserve historical traceability.

---

# 24. RELATIONSHIP WITH ECIP

The Restaurant Organization Model provides the organizational context required by ECIP to:

* Route conversations.
* Escalate customers.
* Select the appropriate employee.
* Determine service availability.
* Build operational context.
* Recommend actions.
* Execute business workflows.

Without understanding the organization, ECIP cannot reason correctly about restaurant operations.

---

# 25. IMPLEMENTATION PRINCIPLE

The Restaurant Organization Model defines the logical business organization of the restaurant.

It does not prescribe:

* Database schema.
* Microservice boundaries.
* User interface.
* API contracts.
* Deployment architecture.

These implementation decisions shall preserve the semantics defined in this document while remaining consistent with the Canonical Enterprise Intelligence Model.

