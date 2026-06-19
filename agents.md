# CodeSudio Real Estate System (Odoo) – Agent Specification

## Overview

This document defines the system design and modules for building a complete **Real Estate Management System in Odoo** for CodeSudio.

The system will handle:
- Property management
- Tenant management
- Rental contracts
- Rent invoicing
- Expenses
- Accounting integration
- ZATCA compliance (Saudi Arabia)
- Reports & analytics

All functionality will be implemented inside **Odoo using custom modules + standard Odoo Accounting**.

---

## System Architecture

### Core Principle
- Odoo is used as the **single unified ERP system**
- Custom modules handle real estate operations
- Odoo Accounting handles invoicing, VAT, and ZATCA compliance
- Avoid splitting into multiple systems

---

## Modules to Build

### 1. Property Management Module
Custom Odoo module: `codesudio_property`

#### Features:
- Buildings management
- Floors (optional)
- Flats / rooms management
- Room status:
  - Available
  - Occupied
  - Maintenance
- Rent amount per unit
- Security deposit tracking
- Room history (tenant assignment log)

---

### 2. Tenant Management
Uses Odoo Contacts + customization

#### Features:
- Tenant profile management
- Mobile number, email
- ID / Iqama number
- VAT number (for companies)
- Emergency contact
- Document uploads (ID, passport, contracts)
- Tenant rental history

---

### 3. Rental Contract Module
Custom module: `codesudio_rental_contract`

#### Features:
- Create rental agreements
- Assign tenant + unit
- Monthly rent setup
- Payment cycle (monthly/quarterly/yearly)
- Contract start and end dates
- Auto invoice generation
- Renewal workflow
- Contract termination
- Unit vacating process

---

### 4. Rent Invoicing (Odoo Accounting)
Uses standard Odoo module: `account`

#### Features:
- Monthly rent invoices
- VAT invoices (Saudi Arabia compliant)
- Credit notes & debit notes
- Payment tracking
- Partial payments support
- Outstanding rent tracking
- Invoice history per tenant

---

### 5. ZATCA Compliance (Saudi Arabia)

Handled through Odoo localization.

#### Key Requirements:
- ZATCA e-invoicing integration
- QR code on invoices
- Structured invoice format (Phase 2 compliance)
- Invoice validation support
- Secure tax reporting

> Recommendation: Do NOT build custom ZATCA logic from scratch. Use Odoo localization and configuration.

---

### 6. Expenses Module
Can use Odoo Expenses / Vendor Bills

#### Features:
- Maintenance costs
- Electricity & water bills
- Cleaning expenses
- Repairs & contractor payments
- Security costs
- Building operational expenses
- Owner-related expenses

---

### 7. Reports & Dashboard

#### Features:
- Rent collection report
- Rent due / overdue report
- Building-wise income report
- Tenant outstanding balance report
- Expense summary report
- Profit analysis report
- VAT report
- Accounting financial reports

---

## Customization Scope

### Required Custom Development
Odoo is not a native real estate system, so the following must be built:

- Property management module
- Rental contract automation
- Room availability logic
- Auto rent invoice generation
- Real estate dashboard
- Tenant history tracking
- Custom receipt print templates
- Rent due automation system

---

## Important Architecture Rules

### 1. Do NOT modify Odoo Accounting heavily
Keep:
- Invoicing
- VAT
- Payments
- ZATCA flow

Stable and standard.

---

### 2. Customization Focus
Only customize:
- Real estate workflows
- UI for property management
- Contract automation

---

### 3. Single System Rule
Avoid:
- Next.js + Odoo split system
- Multiple backend services

Use:
> One system = Odoo only

---

## Final System Summary

The final CodeSudio Odoo system will include:

- Buildings & Property Management
- Flats / Rooms Management
- Tenant Management
- Rental Contracts
- Rent Invoicing
- Receipts & Payments
- Expenses Management
- Reports & Analytics
- Accounting Integration
- VAT Compliance
- ZATCA E-Invoicing (Saudi Arabia)

---

## Goal

Deliver a **fully integrated, scalable, and legally compliant real estate ERP system** for Saudi market using Odoo.

---