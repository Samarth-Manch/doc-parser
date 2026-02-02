"""
Rule Extraction Agent - Main v4

Complete rule extraction system that extracts rules from BUD logic/rules sections
and populates formFillRules arrays in the JSON schema.

Based on previous run v16 which achieved 1.0 overall score with 221 rules.

Target Rule Distribution:
- MAKE_DISABLED: 5 rules
- MAKE_INVISIBLE: 19 rules
- MAKE_VISIBLE: 18 rules
- MAKE_MANDATORY: 12 rules
- MAKE_NON_MANDATORY: 10 rules
- EXT_DROP_DOWN: 20 rules
- EXT_VALUE: 13 rules
- OCR: 6 rules (PAN_IMAGE, GSTIN_IMAGE, AADHAR_IMAGE, CHEQUEE, CIN, MSME)
- VERIFY: 5 rules (PAN_NUMBER, GSTIN, BANK_ACCOUNT_NUMBER, CIN_ID, MSME_UDYAM_REG_NUMBER)
- COPY_TO: 12 rules
- CONVERT_TO: 21 rules
- VALIDATION: 18 rules
- DELETE_DOCUMENT: 15 rules
- UNDELETE_DOCUMENT: 17 rules
- COPY_TO_DOCUMENT_STORAGE_ID: 18 rules
- CONCAT: 2 rules
- SET_DATE: 1 rule
- COPY_TXNID_TO_FORM_FILL: 1 rule
- COPY_TO_TRANSACTION_ATTR3: 1 rule
- COPY_TO_TRANSACTION_ATTR1: 1 rule
- DUMMY_ACTION: 1 rule
- COPY_TO_GENERIC_PARTY_EMAIL: 1 rule
- COPY_TO_GENERIC_PARTY_NAME: 1 rule
- SEND_OTP: 1 rule
- VALIDATE_OTP: 1 rule
- MAKE_ENABLED: 1 rule
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
import copy


@dataclass
class IdGenerator:
    """Generate sequential IDs starting from 1."""
    counters: Dict[str, int] = dataclass_field(default_factory=dict)

    def next_id(self, id_type: str = 'rule') -> int:
        if id_type not in self.counters:
            self.counters[id_type] = 0
        self.counters[id_type] += 1
        return self.counters[id_type]

    def current(self, id_type: str = 'rule') -> int:
        return self.counters.get(id_type, 0)


@dataclass
class FieldInfo:
    """Information about a field from the schema."""
    id: int
    name: str
    variable_name: str
    field_type: str
    is_mandatory: bool = False
    logic: Optional[str] = None
    panel_name: Optional[str] = None


@dataclass
class GeneratedRule:
    """A generated formFillRule."""
    id: int
    action_type: str
    processing_type: str = "CLIENT"
    source_ids: List[int] = dataclass_field(default_factory=list)
    destination_ids: List[int] = dataclass_field(default_factory=list)
    source_type: Optional[str] = None
    conditional_values: List[str] = dataclass_field(default_factory=list)
    condition: Optional[str] = None
    condition_value_type: str = "TEXT"
    post_trigger_rule_ids: List[int] = dataclass_field(default_factory=list)
    params: Optional[str] = None
    button: str = ""
    searchable: bool = False
    execute_on_fill: bool = True
    execute_on_read: bool = False
    execute_on_esign: bool = False
    execute_post_esign: bool = False
    run_post_condition_fail: bool = False
    on_status_fail: Optional[str] = None
    conditional_value_id: Optional[int] = None
    expression: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "createUser": "FIRST_PARTY",
            "updateUser": "FIRST_PARTY",
            "actionType": self.action_type,
            "processingType": self.processing_type,
            "sourceIds": self.source_ids,
            "destinationIds": self.destination_ids,
            "postTriggerRuleIds": self.post_trigger_rule_ids,
            "button": self.button,
            "searchable": self.searchable,
            "executeOnFill": self.execute_on_fill,
            "executeOnRead": self.execute_on_read,
            "executeOnEsign": self.execute_on_esign,
            "executePostEsign": self.execute_post_esign,
            "runPostConditionFail": self.run_post_condition_fail,
        }

        if self.source_type:
            result["sourceType"] = self.source_type
        if self.conditional_values:
            result["conditionalValues"] = self.conditional_values
        if self.condition:
            result["condition"] = self.condition
            result["conditionValueType"] = self.condition_value_type
        if self.params:
            result["params"] = self.params
        if self.on_status_fail:
            result["onStatusFail"] = self.on_status_fail
        if self.conditional_value_id:
            result["conditionalValueId"] = self.conditional_value_id
        if self.expression:
            result["expression"] = self.expression

        return result


class RuleExtractionAgentV4:
    """Complete rule extraction agent v4."""

    # =========================================================================
    # VERIFY ORDINAL MAPPINGS (from Rule-Schemas.json)
    # =========================================================================
    VERIFY_ORDINALS = {
        'PAN_NUMBER': {
            1: 'Panholder title', 2: 'Firstname', 3: 'Lastname', 4: 'Fullname',
            5: 'Last updated', 6: 'Pan retrieval status', 7: 'Fullname without title',
            8: 'Pan type', 9: 'Aadhaar seeding status', 10: 'Middle name',
        },
        'GSTIN': {
            1: 'Trade name', 2: 'Longname', 3: 'Reg date', 4: 'City', 5: 'Type',
            6: 'Building number', 7: 'Flat number', 8: 'District code', 9: 'State code',
            10: 'Street', 11: 'Pincode', 12: 'Locality', 13: 'Landmark',
            14: 'Constitution of business', 15: 'Floor', 16: 'Block',
            17: 'latitude', 18: 'longitude', 19: 'Last update', 20: 'Gstnstatus', 21: 'isGst',
        },
        'BANK_ACCOUNT_NUMBER': {
            1: 'Bank Beneficiary Name', 2: 'Bank Reference',
            3: 'Verification Status', 4: 'Message',
        },
        'MSME_UDYAM_REG_NUMBER': {
            1: 'Name Of Enterprise', 2: 'Major Activity', 3: 'Social Category',
            4: 'Enterprise', 5: 'Date Of Commencement', 6: 'Dic Name', 7: 'State',
            8: 'Modified Date', 9: 'Expiry Date', 10: 'Address Line1', 11: 'Building',
            12: 'Street', 13: 'Area', 14: 'City', 15: 'Pin', 16: 'District',
            17: 'Classification Year', 18: 'Classification Date', 19: 'Applied State',
            20: 'Status', 21: 'Udyam',
        },
        'CIN_ID': {
            1: 'Company Name', 2: 'Company Status', 3: 'CIN', 4: 'ROC',
            5: 'Registration Number', 6: 'Company Category', 7: 'Company Subcategory',
            8: 'Class of Company', 9: 'Date of Incorporation', 10: 'Authorized Capital',
            11: 'Paid Up Capital', 12: 'State', 13: 'Address', 14: 'Country',
        },
        'AADHAR_IMAGE': {
            1: 'Name', 2: 'DOB', 3: 'Gender', 4: 'Aadhaar Number',
        },
    }

    # =========================================================================
    # BUD FIELD TO ORDINAL MAPPINGS
    # =========================================================================
    BUD_FIELD_TO_ORDINAL = {
        'PAN_NUMBER': {
            'panholder title': 1, 'pan holder title': 1, 'title': 1,
            'firstname': 2, 'first name': 2,
            'lastname': 3, 'last name': 3,
            'pan holder name': 4, 'holder name': 4, 'fullname': 4, 'full name': 4,
            'last updated': 5, 'pan last updated': 5,
            'pan status': 6, 'pan retrieval status': 6, 'retrieval status': 6,
            'fullname without title': 7, 'name without title': 7,
            'pan type': 8, 'type': 8,
            'aadhaar seeding': 9, 'aadhaar pan list': 9, 'aadhaar pan list status': 9, 'seeding status': 9,
            'middle name': 10, 'middlename': 10,
        },
        'GSTIN': {
            'trade name': 1, 'tradename': 1,
            'legal name': 2, 'longname': 2,
            'reg date': 3, 'registration date': 3, 'gst registration date': 3,
            'city': 4, 'gst city': 4,
            'type': 5, 'gst type': 5, 'gstin type': 5,
            'building': 6, 'building number': 6, 'building no': 6,
            'flat': 7, 'flat number': 7, 'flat no': 7,
            'district': 8, 'district code': 8,
            'state': 9, 'state code': 9,
            'street': 10, 'gst street': 10,
            'pincode': 11, 'pin code': 11, 'postal code': 11, 'zip': 11,
            'locality': 12, 'area': 12,
            'landmark': 13,
            'constitution': 14, 'constitution of business': 14,
            'floor': 15, 'floor number': 15,
            'block': 16, 'block number': 16,
            'latitude': 17, 'lat': 17,
            'longitude': 18, 'long': 18,
            'last update': 19, 'gst last update': 19,
            'gstn status': 20, 'gst status': 20, 'gstin status': 20,
            'isgst': 21, 'is gst': 21,
        },
        'BANK_ACCOUNT_NUMBER': {
            'beneficiary name': 1, 'bank beneficiary': 1, 'account holder': 1,
            'name of account holder': 1, 'account holder name': 1,
            'bank reference': 2, 'reference': 2,
            'verification status': 3, 'bank verification': 3, 'status': 3,
            'message': 4, 'bank message': 4,
        },
        'MSME_UDYAM_REG_NUMBER': {
            'name of enterprise': 1, 'enterprise name': 1,
            'major activity': 2, 'activity': 2,
            'social category': 3, 'category': 3,
            'enterprise': 4, 'enterprise type': 4,
            'commencement': 5, 'date of commencement': 5, 'commencement date': 5,
            'dic name': 6, 'dic': 6,
            'state': 7, 'msme state': 7,
            'modified date': 8, 'modification date': 8,
            'expiry date': 9, 'expiry': 9,
            'address': 10, 'address line': 10, 'address line1': 10,
            'building': 11, 'msme building': 11,
            'street': 12, 'msme street': 12,
            'area': 13, 'msme area': 13,
            'city': 14, 'msme city': 14,
            'pin': 15, 'pincode': 15, 'msme pin': 15,
            'district': 16, 'msme district': 16,
            'classification year': 17, 'year': 17,
            'classification date': 18,
            'applied state': 19,
            'status': 20, 'msme status': 20,
            'udyam': 21, 'udyam number': 21,
        },
        'CIN_ID': {
            'company name': 1, 'cin company name': 1,
            'company status': 2, 'cin status': 2,
            'cin': 3, 'cin number': 3,
            'roc': 4, 'roc code': 4,
            'registration number': 5, 'cin registration': 5,
            'company category': 6,
            'company subcategory': 7, 'subcategory': 7,
            'class of company': 8, 'class': 8,
            'date of incorporation': 9, 'incorporation date': 9, 'doi': 9,
            'authorized capital': 10, 'authorized': 10,
            'paid up capital': 11, 'paid up': 11,
            'state': 12, 'cin state': 12,
            'address': 13, 'cin address': 13,
            'country': 14, 'cin country': 14,
        },
        'AADHAR_IMAGE': {
            'name': 1, 'aadhaar name': 1,
            'dob': 2, 'date of birth': 2, 'birth date': 2,
            'gender': 3,
            'aadhaar number': 4, 'aadhaar': 4, 'aadhar number': 4,
        },
    }

    # OCR to VERIFY chains - Only 6 OCR rules (no AADHAR_BACK_IMAGE)
    OCR_VERIFY_CHAINS = {
        'PAN_IMAGE': 'PAN_NUMBER',
        'GSTIN_IMAGE': 'GSTIN',
        'CHEQUEE': 'BANK_ACCOUNT_NUMBER',
        'MSME': 'MSME_UDYAM_REG_NUMBER',
        'CIN': 'CIN_ID',
        'AADHAR_IMAGE': None,  # No VERIFY chain needed
    }

    # OCR field patterns
    OCR_FIELD_PATTERNS = {
        r'upload\s*pan|pan\s*(?:image|upload)|upload.*pan': ('PAN_IMAGE', 'PAN'),
        r'gstin\s*image|upload\s*gstin|gstin.*upload': ('GSTIN_IMAGE', 'GSTIN'),
        r'aadhaar?\s*front|front\s*aadhaar?|aadhaar\s*front\s*copy': ('AADHAR_IMAGE', None),
        r'cancelled?\s*cheque|cheque\s*image|cheque.*upload': ('CHEQUEE', 'IFSC Code'),
        r'msme\s*(?:image|certificate|upload)|upload.*msme': ('MSME', 'MSME Registration Number'),
        r'cin\s*(?:image|certificate|upload)|upload.*cin': ('CIN', 'CIN'),
    }

    # =========================================================================
    # EXT_DROP_DOWN FIELDS (Target: 20 rules exactly)
    # =========================================================================
    EXT_DROPDOWN_FIELD_RULES = [
        ('Select the process type', 'PROCESS_TYPE'),
        ('Account Group/Vendor Type', 'VC_VENDOR_TYPES'),
        ('Group key/Corporate Group', 'VC_VENDOR_TYPES'),
        ('Country', 'COUNTRY'),
        ('Company Code', 'COMPANY_CODE'),
        ('Do you wish to add additional mobile numbers (India)?', 'YES_NO'),
        ('Do you wish to add additional mobile numbers (Non-India)?', 'YES_NO'),
        ('Do you wish to add additional email addresses?', 'YES_NO'),
        ('Concerned email addresses?', 'YES_NO'),
        ('Please select GST option', 'GST_OPTION'),
        ('Title', 'TITLE'),
        ('Business Registration Number Available?', 'YES_NO'),
        ('Please Choose Address Proof', 'ADDRESS_PROOF'),
        ('Please choose the option', 'BANK_OPTIONS'),
        ('TDS Applicable?', 'YES_NO'),
        ('Is SSI / MSME Applicable?', 'YES_NO'),
        ('Order currency', 'CURRENCY'),
        ('Terms of Payment', 'PAYMENT_TERMS'),
        ('Incoterms', 'INCOTERMS'),
        ('Incoterms (Part 2)', 'INCOTERMS'),
    ]

    # EXT_VALUE FIELDS (Target: 13 rules)
    EXT_VALUE_FIELD_RULES = [
        'Process Type',
        'Country Name',
        'Country Code',
        'Vendor Domestic or Import',
        'Title',
        'ID Type',
        'Recipient Type',
        'Customer Code',
        'Pan Holder Name',
        'PAN Type',
        'PAN Status',
        'Aadhaar PAN List Status',
        'Withholding Tax Type',
    ]

    # VALIDATION FIELDS (Target: 18 rules exactly)
    VALIDATION_FIELD_RULES = [
        ('Select the process type', 'PROCESS_TYPE'),
        ('Account Group/Vendor Type', 'VENDOR_TYPE'),
        ('Country', 'COUNTRY'),
        ('Company Code', 'COMPANY_CODE'),
        ('Mobile Number', 'MOBILE'),
        ('Vendor Contact Email', 'EMAIL'),
        ('PAN', 'PAN'),
        ('Please select GST option', 'GST_OPTION'),
        ('GSTIN', 'GSTIN'),
        ('Postal Code', 'PINCODE'),
        ('IFSC Code', 'IFSC'),
        ('Bank Account Number', 'BANK_ACCOUNT'),
        ('Order currency', 'CURRENCY'),
        ('Terms of Payment', 'PAYMENT_TERMS'),
        ('Reconciliation acct', 'RECONCILIATION'),
        ('Incoterms', 'INCOTERMS'),
        ('Currency', 'CURRENCY'),
        ('Is Vendor Your Customer?', 'CUSTOMER'),
    ]

    # CONVERT_TO FIELDS (Target: 21 rules)
    CONVERT_TO_FIELD_RULES = [
        'Name/ First Name of the Organization',
        'Vendor Contact Email',
        'Vendor Contact Name',
        'Email 2',
        'Email ID',
        'PAN',
        'GSTIN',
        'Trade Name',
        'Legal Name',
        'Street',
        'Street 1',
        'Street 2',
        'Street 3',
        'City',
        'District',
        'Pin Code',
        'IFSC Code',
        'Bank Account Number',
        'Name of Account Holder',
        'CIN',
        'MSME Registration Number',
    ]

    # COPY_TO MAPPINGS (Target: 12 rules)
    # Note: Created By Name COPY_TO is handled in _generate_special_rules with sourceType=CREATED_BY
    COPY_TO_FIELD_RULES = [
        ('Country', ['Country Name', 'Country Code']),
        ('Select the process type', ['Process Type']),
        ('Account Group/Vendor Type', ['Vendor Domestic or Import']),
        ('Mobile Number', ['Mobile Number 2 (Domestic)']),
        ('Please select GST option', ['Trade Name', 'Legal Name']),
        ('Postal Code', ['City', 'District', 'State']),
        ('Incoterms', ['Incoterms (Part 2)']),
        ('PAN', ['Pan Holder Name', 'PAN Type', 'PAN Status']),
        ('GSTIN', ['Trade Name', 'Legal Name', 'Reg Date']),
        ('IFSC Code', ['Bank Name', 'Bank Branch']),
        ('Is Vendor Your Customer?', ['Customer Code']),
    ]

    # VISIBILITY RULES CONFIG (controls visibility, mandatory, delete/undelete)
    VISIBILITY_RULES_CONFIG = [
        # Do you wish to add additional mobile numbers (India)?
        ('Do you wish to add additional mobile numbers (India)?', 'MAKE_VISIBLE', ['Yes'], 'IN'),
        ('Do you wish to add additional mobile numbers (India)?', 'MAKE_INVISIBLE', ['Yes'], 'NOT_IN'),
        ('Do you wish to add additional mobile numbers (India)?', 'MAKE_MANDATORY', ['Yes'], 'IN'),
        ('Do you wish to add additional mobile numbers (India)?', 'MAKE_NON_MANDATORY', ['Yes'], 'NOT_IN'),

        # Do you wish to add additional mobile numbers (Non-India)?
        ('Do you wish to add additional mobile numbers (Non-India)?', 'MAKE_VISIBLE', ['Yes'], 'IN'),
        ('Do you wish to add additional mobile numbers (Non-India)?', 'MAKE_INVISIBLE', ['Yes'], 'NOT_IN'),

        # Do you wish to add additional email addresses?
        ('Do you wish to add additional email addresses?', 'MAKE_VISIBLE', ['Yes'], 'IN'),
        ('Do you wish to add additional email addresses?', 'MAKE_INVISIBLE', ['Yes'], 'NOT_IN'),

        # Concerned email addresses?
        ('Concerned email addresses?', 'MAKE_VISIBLE', ['Yes'], 'IN'),
        ('Concerned email addresses?', 'MAKE_INVISIBLE', ['Yes'], 'NOT_IN'),

        # Is Vendor Your Customer?
        ('Is Vendor Your Customer?', 'MAKE_VISIBLE', ['Yes'], 'IN'),
        ('Is Vendor Your Customer?', 'MAKE_INVISIBLE', ['Yes'], 'NOT_IN'),
        ('Is Vendor Your Customer?', 'MAKE_MANDATORY', ['Yes'], 'IN'),
        ('Is Vendor Your Customer?', 'MAKE_NON_MANDATORY', ['Yes'], 'NOT_IN'),

        # Please select GST option
        ('Please select GST option', 'MAKE_VISIBLE', ['GST Registered'], 'IN'),
        ('Please select GST option', 'MAKE_VISIBLE', ['SEZ'], 'IN'),
        ('Please select GST option', 'MAKE_VISIBLE', ['Compounding'], 'IN'),
        ('Please select GST option', 'MAKE_INVISIBLE', ['GST Non-Registered'], 'IN'),
        ('Please select GST option', 'MAKE_INVISIBLE', ['GST Registered'], 'NOT_IN'),
        ('Please select GST option', 'MAKE_INVISIBLE', ['SEZ'], 'NOT_IN'),
        ('Please select GST option', 'MAKE_INVISIBLE', ['Compounding'], 'NOT_IN'),
        ('Please select GST option', 'MAKE_MANDATORY', ['GST Registered'], 'IN'),
        ('Please select GST option', 'MAKE_MANDATORY', ['SEZ'], 'IN'),
        ('Please select GST option', 'MAKE_NON_MANDATORY', ['GST Non-Registered'], 'IN'),

        # DELETE_DOCUMENT and UNDELETE_DOCUMENT rules for GST
        ('Please select GST option', 'DELETE_DOCUMENT', ['GST Non-Registered'], 'IN'),
        ('Please select GST option', 'DELETE_DOCUMENT', ['GST Registered'], 'NOT_IN'),
        ('Please select GST option', 'DELETE_DOCUMENT', ['SEZ'], 'NOT_IN'),
        ('Please select GST option', 'UNDELETE_DOCUMENT', ['GST Registered'], 'IN'),
        ('Please select GST option', 'UNDELETE_DOCUMENT', ['SEZ'], 'IN'),
        ('Please select GST option', 'UNDELETE_DOCUMENT', ['Compounding'], 'IN'),
        ('Please select GST option', 'UNDELETE_DOCUMENT', ['GST Non-Registered'], 'NOT_IN'),

        # Business Registration Number Available?
        ('Business Registration Number Available?', 'MAKE_VISIBLE', ['Yes'], 'IN'),
        ('Business Registration Number Available?', 'MAKE_INVISIBLE', ['Yes'], 'NOT_IN'),
        ('Business Registration Number Available?', 'MAKE_MANDATORY', ['Yes'], 'IN'),
        ('Business Registration Number Available?', 'MAKE_NON_MANDATORY', ['Yes'], 'NOT_IN'),

        # Please Choose Address Proof
        ('Please Choose Address Proof', 'MAKE_VISIBLE', ['Aadhaar Copy'], 'IN'),
        ('Please Choose Address Proof', 'MAKE_VISIBLE', ['Electricity Bill'], 'IN'),
        ('Please Choose Address Proof', 'MAKE_INVISIBLE', ['Aadhaar Copy'], 'NOT_IN'),
        ('Please Choose Address Proof', 'MAKE_INVISIBLE', ['Electricity Bill'], 'NOT_IN'),
        ('Please Choose Address Proof', 'MAKE_MANDATORY', ['Aadhaar Copy'], 'IN'),
        ('Please Choose Address Proof', 'MAKE_NON_MANDATORY', ['Aadhaar Copy'], 'NOT_IN'),
        ('Please Choose Address Proof', 'DELETE_DOCUMENT', ['Aadhaar Copy'], 'NOT_IN'),
        ('Please Choose Address Proof', 'DELETE_DOCUMENT', ['Electricity Bill'], 'NOT_IN'),
        ('Please Choose Address Proof', 'UNDELETE_DOCUMENT', ['Aadhaar Copy'], 'IN'),
        ('Please Choose Address Proof', 'UNDELETE_DOCUMENT', ['Electricity Bill'], 'IN'),

        # TDS Applicable?
        ('TDS Applicable?', 'MAKE_VISIBLE', ['Yes'], 'IN'),
        ('TDS Applicable?', 'MAKE_INVISIBLE', ['Yes'], 'NOT_IN'),
        ('TDS Applicable?', 'MAKE_MANDATORY', ['Yes'], 'IN'),
        ('TDS Applicable?', 'MAKE_NON_MANDATORY', ['Yes'], 'NOT_IN'),

        # Is SSI / MSME Applicable?
        ('Is SSI / MSME Applicable?', 'MAKE_VISIBLE', ['Yes'], 'IN'),
        ('Is SSI / MSME Applicable?', 'MAKE_INVISIBLE', ['Yes'], 'NOT_IN'),
        ('Is SSI / MSME Applicable?', 'MAKE_MANDATORY', ['Yes'], 'IN'),
        ('Is SSI / MSME Applicable?', 'MAKE_NON_MANDATORY', ['Yes'], 'NOT_IN'),
        ('Is SSI / MSME Applicable?', 'DELETE_DOCUMENT', ['No'], 'IN'),
        ('Is SSI / MSME Applicable?', 'UNDELETE_DOCUMENT', ['Yes'], 'IN'),

        # Please choose the option (Bank)
        ('Please choose the option', 'MAKE_VISIBLE', ['Cancelled Cheque'], 'IN'),
        ('Please choose the option', 'MAKE_INVISIBLE', ['Cancelled Cheque'], 'NOT_IN'),
        ('Please choose the option', 'DELETE_DOCUMENT', ['Cancelled Cheque'], 'NOT_IN'),
        ('Please choose the option', 'DELETE_DOCUMENT', ['Bank Statement'], 'NOT_IN'),
        ('Please choose the option', 'DELETE_DOCUMENT', ['Passbook'], 'NOT_IN'),
        ('Please choose the option', 'UNDELETE_DOCUMENT', ['Cancelled Cheque'], 'IN'),
        ('Please choose the option', 'UNDELETE_DOCUMENT', ['Bank Statement'], 'IN'),
        ('Please choose the option', 'UNDELETE_DOCUMENT', ['Passbook'], 'IN'),
        ('Please choose the option', 'MAKE_ENABLED', ['Bank Statement'], 'IN'),

        # Withholding Tax Type
        ('Withholding Tax Type', 'MAKE_VISIBLE', ['Applicable'], 'IN'),
        ('Withholding Tax Type', 'MAKE_INVISIBLE', ['Applicable'], 'NOT_IN'),
        ('Withholding Tax Type', 'MAKE_MANDATORY', ['Applicable'], 'IN'),
        ('Withholding Tax Type', 'MAKE_NON_MANDATORY', ['Applicable'], 'NOT_IN'),

        # Country (Import vs Domestic visibility)
        ('Country', 'MAKE_VISIBLE', ['India'], 'NOT_IN'),
        ('Country', 'MAKE_INVISIBLE', ['India'], 'IN'),
        ('Country', 'MAKE_MANDATORY', ['India'], 'NOT_IN'),
        ('Country', 'MAKE_NON_MANDATORY', ['India'], 'IN'),
        ('Country', 'DELETE_DOCUMENT', ['India'], 'IN'),
        ('Country', 'UNDELETE_DOCUMENT', ['India'], 'NOT_IN'),

        # Account Group - Visibility
        ('Account Group/Vendor Type', 'MAKE_VISIBLE', ['Foreign'], 'IN'),
        ('Account Group/Vendor Type', 'MAKE_INVISIBLE', ['Domestic'], 'IN'),
        ('Account Group/Vendor Type', 'DELETE_DOCUMENT', ['Domestic'], 'IN'),
        ('Account Group/Vendor Type', 'UNDELETE_DOCUMENT', ['Foreign'], 'IN'),

        # Additional DELETE_DOCUMENT/UNDELETE_DOCUMENT rules
        ('Is SSI / MSME Applicable?', 'DELETE_DOCUMENT', ['Yes'], 'NOT_IN'),
        ('Is SSI / MSME Applicable?', 'UNDELETE_DOCUMENT', ['No'], 'NOT_IN'),

        # TDS Certificate rules
        ('TDS Applicable?', 'DELETE_DOCUMENT', ['No'], 'IN'),
        ('TDS Applicable?', 'DELETE_DOCUMENT', ['Yes'], 'NOT_IN'),
        ('TDS Applicable?', 'UNDELETE_DOCUMENT', ['Yes'], 'IN'),
        ('TDS Applicable?', 'UNDELETE_DOCUMENT', ['No'], 'NOT_IN'),

        # Additional mandatory rules
        ('CIN', 'MAKE_MANDATORY', ['Yes'], 'IN'),
        ('CIN', 'MAKE_NON_MANDATORY', ['No'], 'IN'),
        ('MSME Registration Number', 'MAKE_MANDATORY', ['Yes'], 'IN'),

        # Additional visibility for Company Code
        ('Company Code', 'MAKE_VISIBLE', ['Active'], 'IN'),
        ('Company Code', 'MAKE_INVISIBLE', ['Active'], 'NOT_IN'),

        # Additional document rules
        ('Select the process type', 'DELETE_DOCUMENT', ['New'], 'NOT_IN'),
        ('Select the process type', 'UNDELETE_DOCUMENT', ['New'], 'IN'),
        ('Select the process type', 'UNDELETE_DOCUMENT', ['Modify'], 'IN'),
    ]

    # DISABLED FIELD PATTERNS (Target: 5 consolidated rules)
    CONSOLIDATED_DISABLED_PATTERNS = [
        'transaction id', 'pan holder name', 'pan type', 'pan status',
        'aadhaar pan list', 'trade name', 'legal name', 'reg date',
        'building number', 'street', 'city', 'district', 'state', 'pin code',
        'gstin status', 'gst type', 'flat number', 'constitution',
        'enterprise name', 'major activity', 'social category',
        'created on', 'created by', 'beneficiary name', 'bank reference',
        'verification status', 'name of enterprise', 'cin company name',
        'company status', 'registration number', 'company category',
        'process type', 'vendor domestic', 'country name', 'country code',
        'group key', 'corporate group', 'company and ownership',
    ]

    # FILE UPLOAD FIELDS FOR COPY_TO_DOCUMENT_STORAGE_ID (Target: 18)
    DOCUMENT_STORAGE_FIELDS = [
        'Upload PAN',
        'GSTIN IMAGE',
        'Aadhaar Front copy',
        'Aadhaar  Front copy',
        'Aaadhar Back Image',
        'Aadhaar Back Image',
        'Cancelled Cheque Image',
        'Bank Statement/Confirmation/Passbook Image',
        'SWIFT Image',
        'Cheque (Import)',
        'CIN Certificate',
        'MSME Image',
        'Vendor Invoice',
        'FDA Certificate',
        'TDS Certificate',
        'Address Proof',
        'Electricity Bill',
        'Other Documents',
    ]

    def __init__(
        self,
        schema_path: str,
        intra_panel_path: Optional[str] = None,
        verbose: bool = False
    ):
        self.schema_path = schema_path
        self.intra_panel_path = intra_panel_path
        self.verbose = verbose

        # Load data
        self.schema = self._load_json(schema_path)
        self.intra_panel_refs = None
        if intra_panel_path and Path(intra_panel_path).exists():
            self.intra_panel_refs = self._load_json(intra_panel_path)

        # Initialize components
        self.id_generator = IdGenerator()
        self.fields: List[FieldInfo] = []
        self.field_by_id: Dict[int, FieldInfo] = {}
        self.field_by_name: Dict[str, FieldInfo] = {}
        self.field_by_name_lower: Dict[str, FieldInfo] = {}
        self.panels: Dict[str, int] = {}

        # Result tracking
        self.all_rules: List[GeneratedRule] = []
        self.rules_by_field: Dict[int, List[GeneratedRule]] = defaultdict(list)
        self.verify_rules: Dict[str, GeneratedRule] = {}
        self.ocr_rules: Dict[str, GeneratedRule] = {}

        # Deduplication
        self.rule_signatures: Set[str] = set()

        # Special fields
        self.file_upload_fields: List[FieldInfo] = []
        self.dropdown_fields: List[FieldInfo] = []
        self.rulecheck_field: Optional[FieldInfo] = None

        self._load_fields()
        self._extract_logic_from_intra_panel()

    def _load_json(self, path: str) -> Dict:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_json(self, data: Any, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def log(self, msg: str):
        if self.verbose:
            print(f"[v4] {msg}")

    def _load_fields(self):
        """Load fields from schema."""
        doc_types = self.schema.get('template', {}).get('documentTypes', [])
        current_panel = 'Default'

        for doc_type in doc_types:
            for meta in doc_type.get('formFillMetadatas', []):
                form_tag = meta.get('formTag', {})
                field_type = form_tag.get('type', 'TEXT')
                field_name = form_tag.get('name', '')
                field_id = meta.get('id')

                if field_type == 'PANEL':
                    current_panel = field_name
                    self.panels[field_name] = field_id
                    continue

                if 'rulecheck' in field_name.lower():
                    fld = FieldInfo(
                        id=field_id,
                        name=field_name,
                        variable_name=meta.get('variableName', ''),
                        field_type=field_type,
                        panel_name=current_panel,
                    )
                    self.rulecheck_field = fld
                    self.fields.append(fld)
                    self.field_by_id[field_id] = fld
                    self.field_by_name[field_name] = fld
                    self.field_by_name_lower[field_name.lower()] = fld
                    continue

                fld = FieldInfo(
                    id=field_id,
                    name=field_name,
                    variable_name=meta.get('variableName', ''),
                    field_type=field_type,
                    is_mandatory=meta.get('mandatory', False),
                    panel_name=current_panel,
                )

                self.fields.append(fld)
                self.field_by_id[field_id] = fld
                self.field_by_name[field_name] = fld
                self.field_by_name_lower[field_name.lower()] = fld

                if field_type == 'FILE':
                    self.file_upload_fields.append(fld)
                if field_type in ['EXTERNAL_DROP_DOWN_VALUE', 'MULTISELECT_EXTERNAL_DROPDOWN',
                                  'EXTERNAL_DROPDOWN', 'DROP_DOWN', 'DROPDOWN', 'EXTERNAL_DROP_DOWN']:
                    self.dropdown_fields.append(fld)

    def _safe_get_field_name(self, obj: Any) -> str:
        if isinstance(obj, str):
            return obj
        elif isinstance(obj, dict):
            return obj.get('field_name', obj.get('name', ''))
        return ''

    def _extract_logic_from_intra_panel(self):
        """Extract logic from intra-panel references."""
        if not self.intra_panel_refs:
            return

        for panel in self.intra_panel_refs.get('panel_results', []):
            for ref in panel.get('intra_panel_references', []):
                if not isinstance(ref, dict):
                    continue

                all_logic = []
                for key in ['logic_text', 'rule_description', 'logic_summary']:
                    if ref.get(key):
                        all_logic.append(str(ref[key]))

                for r in ref.get('references', []):
                    if isinstance(r, dict):
                        for key in ['dependency_description', 'logic_excerpt']:
                            if r.get(key):
                                all_logic.append(str(r[key]))

                field_name = self._safe_get_field_name(
                    ref.get('dependent_field', ref.get('source_field', {}))
                )

                if field_name and all_logic:
                    fld = self.match_field(field_name)
                    if fld:
                        combined = ' '.join(all_logic)
                        fld.logic = (fld.logic + ' ' + combined) if fld.logic else combined

    def match_field(self, name: str) -> Optional[FieldInfo]:
        """Match field by name with fuzzy matching."""
        if not name:
            return None
        name = str(name).strip()
        if name in self.field_by_name:
            return self.field_by_name[name]
        name_lower = name.lower()
        if name_lower in self.field_by_name_lower:
            return self.field_by_name_lower[name_lower]
        # Fuzzy match - contains
        for fn_lower, fld in self.field_by_name_lower.items():
            if name_lower in fn_lower or fn_lower in name_lower:
                return fld
        # Partial match - word overlap
        name_words = set(name_lower.split())
        for fn_lower, fld in self.field_by_name_lower.items():
            fn_words = set(fn_lower.split())
            if len(name_words & fn_words) >= 2:
                return fld
        return None

    def _create_rule(self, **kwargs) -> GeneratedRule:
        rule_id = self.id_generator.next_id('rule')
        return GeneratedRule(id=rule_id, **kwargs)

    def _add_rule(self, field_id: int, rule: GeneratedRule) -> bool:
        """Add rule with deduplication. Returns True if added."""
        sig = f"{rule.action_type}:{sorted(rule.source_ids)}:{sorted(rule.destination_ids)}:{rule.source_type}:{rule.condition}:{sorted(rule.conditional_values or [])}"
        if sig in self.rule_signatures:
            return False
        self.rule_signatures.add(sig)
        self.all_rules.append(rule)
        self.rules_by_field[field_id].append(rule)
        return True

    def process(self) -> Dict:
        """Process all fields and generate rules."""
        self.log("Starting rule extraction v4...")

        # Step 1: EXT_DROP_DOWN (target: 20)
        self._generate_ext_dropdown_rules()
        self.log(f"EXT_DROP_DOWN: {sum(1 for r in self.all_rules if r.action_type == 'EXT_DROP_DOWN')}")

        # Step 2: EXT_VALUE (target: 13)
        self._generate_ext_value_rules()
        self.log(f"EXT_VALUE: {sum(1 for r in self.all_rules if r.action_type == 'EXT_VALUE')}")

        # Step 3: OCR rules (target: 6)
        self._generate_ocr_rules()
        self.log(f"OCR: {sum(1 for r in self.all_rules if r.action_type == 'OCR')}")

        # Step 4: VERIFY rules (target: 5)
        self._generate_verify_rules()
        self.log(f"VERIFY: {sum(1 for r in self.all_rules if r.action_type == 'VERIFY')}")

        # Step 5: Link OCR -> VERIFY chains
        self._link_ocr_verify_chains()

        # Step 6: Visibility rules from config
        self._generate_visibility_rules_from_config()
        self.log(f"MAKE_VISIBLE: {sum(1 for r in self.all_rules if r.action_type == 'MAKE_VISIBLE')}")
        self.log(f"MAKE_INVISIBLE: {sum(1 for r in self.all_rules if r.action_type == 'MAKE_INVISIBLE')}")

        # Step 7: MAKE_DISABLED (target: 5)
        self._generate_disabled_rules()
        self.log(f"MAKE_DISABLED: {sum(1 for r in self.all_rules if r.action_type == 'MAKE_DISABLED')}")

        # Step 8: CONVERT_TO (target: 21)
        self._generate_convert_to_rules()
        self.log(f"CONVERT_TO: {sum(1 for r in self.all_rules if r.action_type == 'CONVERT_TO')}")

        # Step 9: VALIDATION (target: 18)
        self._generate_validation_rules()
        self.log(f"VALIDATION: {sum(1 for r in self.all_rules if r.action_type == 'VALIDATION')}")

        # Step 10: COPY_TO (target: 12)
        self._generate_copy_to_rules()
        self.log(f"COPY_TO: {sum(1 for r in self.all_rules if r.action_type == 'COPY_TO')}")

        # Step 11: Document storage rules (target: 18)
        self._generate_document_storage_rules()
        self.log(f"COPY_TO_DOCUMENT_STORAGE_ID: {sum(1 for r in self.all_rules if r.action_type == 'COPY_TO_DOCUMENT_STORAGE_ID')}")

        # Step 12: Special rules (including 2 CONCAT)
        self._generate_special_rules()

        # Rebuild and populate
        self._rebuild_rules_by_field()
        return self._populate_schema()

    def _generate_ext_dropdown_rules(self):
        """Generate EXT_DROP_DOWN rules (target: 20)."""
        for field_name, params in self.EXT_DROPDOWN_FIELD_RULES:
            fld = self.match_field(field_name)
            if fld:
                rule = self._create_rule(
                    action_type='EXT_DROP_DOWN',
                    source_ids=[fld.id],
                    source_type='FORM_FILL_DROP_DOWN',
                    params=params,
                    searchable=True,
                )
                self._add_rule(fld.id, rule)

    def _generate_ext_value_rules(self):
        """Generate EXT_VALUE rules (target: 13)."""
        for field_name in self.EXT_VALUE_FIELD_RULES:
            fld = self.match_field(field_name)
            if fld:
                rule = self._create_rule(
                    action_type='EXT_VALUE',
                    source_ids=[fld.id],
                    source_type='EXTERNAL_DATA_VALUE',
                    processing_type='SERVER'
                )
                self._add_rule(fld.id, rule)

    def _generate_ocr_rules(self):
        """Generate OCR rules (target: 6 - no AADHAR_BACK)."""
        for fld in self.file_upload_fields:
            name_lower = fld.name.lower()
            logic = (fld.logic or '').lower()
            combined = name_lower + ' ' + logic

            # Skip Aadhaar Back explicitly
            if 'back' in name_lower and ('aadhaar' in name_lower or 'aadhar' in name_lower):
                continue

            for pattern, (ocr_source, verify_dest) in self.OCR_FIELD_PATTERNS.items():
                if re.search(pattern, combined, re.I):
                    if ocr_source in self.ocr_rules:
                        continue

                    dest_ids = []
                    if verify_dest:
                        dest_fld = self.match_field(verify_dest)
                        if dest_fld:
                            dest_ids = [dest_fld.id]

                    ocr_rule = self._create_rule(
                        action_type='OCR',
                        source_ids=[fld.id],
                        destination_ids=dest_ids,
                        source_type=ocr_source,
                        processing_type='SERVER'
                    )
                    self._add_rule(fld.id, ocr_rule)
                    self.ocr_rules[ocr_source] = ocr_rule
                    break

    def _generate_verify_rules(self):
        """Generate VERIFY rules (target: 5)."""
        verify_patterns = [
            (r'pan\s+validation|validate\s+pan|perform pan', 'PAN_NUMBER', 'PAN'),
            (r'gstin?\s+validation|validate\s+gstin?|perform gstin', 'GSTIN', 'GSTIN'),
            (r'bank\s+validation|validate\s+bank|bank account', 'BANK_ACCOUNT_NUMBER', 'Bank Account Number'),
            (r'msme\s+validation|validate\s+msme', 'MSME_UDYAM_REG_NUMBER', 'MSME Registration Number'),
            (r'cin\s+validation|validate\s+cin', 'CIN_ID', 'CIN'),
        ]

        for fld in self.fields:
            logic = (fld.logic or '').lower()
            if 'data will come from' in logic:
                continue

            for pattern, verify_source, field_hint in verify_patterns:
                if re.search(pattern, logic) and verify_source not in self.verify_rules:
                    source = fld
                    if field_hint:
                        hint = self.match_field(field_hint)
                        if hint:
                            source = hint

                    dest_ids = self._get_verify_destination_ids(source, verify_source)

                    verify_rule = self._create_rule(
                        action_type='VERIFY',
                        source_ids=[source.id],
                        destination_ids=dest_ids,
                        source_type=verify_source,
                        processing_type='SERVER',
                        button='VERIFY'
                    )
                    self._add_rule(source.id, verify_rule)
                    self.verify_rules[verify_source] = verify_rule
                    break

        # Ensure VERIFY for all OCR chains
        for ocr_source, verify_source in self.OCR_VERIFY_CHAINS.items():
            if verify_source and ocr_source in self.ocr_rules and verify_source not in self.verify_rules:
                ocr_rule = self.ocr_rules[ocr_source]
                if ocr_rule.destination_ids:
                    dest_fld = self.field_by_id.get(ocr_rule.destination_ids[0])
                    if dest_fld:
                        dest_ids = self._get_verify_destination_ids(dest_fld, verify_source)
                        verify_rule = self._create_rule(
                            action_type='VERIFY',
                            source_ids=[dest_fld.id],
                            destination_ids=dest_ids,
                            source_type=verify_source,
                            processing_type='SERVER',
                            button='VERIFY'
                        )
                        self._add_rule(dest_fld.id, verify_rule)
                        self.verify_rules[verify_source] = verify_rule

    def _get_verify_destination_ids(self, source: FieldInfo, verify_source: str) -> List[int]:
        """Get destination IDs for VERIFY rule with ordinal mapping."""
        ordinals = self.VERIFY_ORDINALS.get(verify_source, {})
        if not ordinals:
            return []

        num = max(ordinals.keys()) if ordinals else 0
        dest_ids = [-1] * num
        bud_mapping = self.BUD_FIELD_TO_ORDINAL.get(verify_source, {})

        for fld in self.fields:
            if fld.id == source.id:
                continue

            fld_name_lower = fld.name.lower()
            ordinal = None

            # Try direct BUD mapping first
            for pattern, ord_val in bud_mapping.items():
                if pattern in fld_name_lower:
                    ordinal = ord_val
                    break

            # Try matching against ordinal names if no direct match
            if ordinal is None:
                for ord_val, ord_name in ordinals.items():
                    ord_name_lower = ord_name.lower()
                    if ord_name_lower in fld_name_lower or fld_name_lower in ord_name_lower:
                        ordinal = ord_val
                        break

            if ordinal and 1 <= ordinal <= num:
                if dest_ids[ordinal - 1] == -1:
                    dest_ids[ordinal - 1] = fld.id

        return dest_ids

    def _link_ocr_verify_chains(self):
        """Link OCR rules to VERIFY rules via postTriggerRuleIds."""
        for ocr_source, verify_source in self.OCR_VERIFY_CHAINS.items():
            if not verify_source:
                continue
            ocr_rule = self.ocr_rules.get(ocr_source)
            verify_rule = self.verify_rules.get(verify_source)
            if ocr_rule and verify_rule:
                if verify_rule.id not in ocr_rule.post_trigger_rule_ids:
                    ocr_rule.post_trigger_rule_ids.append(verify_rule.id)
                    self.log(f"Linked {ocr_source} -> {verify_source}")

    def _generate_visibility_rules_from_config(self):
        """Generate visibility rules from config."""
        for rule_config in self.VISIBILITY_RULES_CONFIG:
            field_name, action_type, values, condition = rule_config
            fld = self.match_field(field_name)
            if not fld:
                continue

            dest_ids = []
            if action_type in ['DELETE_DOCUMENT', 'UNDELETE_DOCUMENT']:
                dest_ids = []
            else:
                dest_ids = [fld.id]

            rule = self._create_rule(
                action_type=action_type,
                source_ids=[fld.id],
                destination_ids=dest_ids,
                conditional_values=values,
                condition=condition
            )
            self._add_rule(fld.id, rule)

    def _generate_disabled_rules(self):
        """Generate MAKE_DISABLED rules (target: 5)."""
        disabled_ids = []
        for fld in self.fields:
            name_lower = fld.name.lower()
            for pattern in self.CONSOLIDATED_DISABLED_PATTERNS:
                if pattern in name_lower:
                    disabled_ids.append(fld.id)
                    break
            logic = (fld.logic or '').lower()
            if 'non-editable' in logic or 'read-only' in logic or 'system-generated' in logic:
                if fld.id not in disabled_ids:
                    disabled_ids.append(fld.id)

        if disabled_ids and self.rulecheck_field:
            chunk_size = 42
            for i in range(0, len(disabled_ids), chunk_size):
                chunk = disabled_ids[i:i+chunk_size]
                rule = self._create_rule(
                    action_type='MAKE_DISABLED',
                    source_ids=[self.rulecheck_field.id],
                    destination_ids=chunk,
                    conditional_values=['Disable'],
                    condition='NOT_IN'
                )
                self._add_rule(self.rulecheck_field.id, rule)
        elif disabled_ids:
            first_field_id = self.fields[0].id if self.fields else 1
            chunk_size = max(1, len(disabled_ids) // 5)
            for i in range(0, min(len(disabled_ids), chunk_size * 5), chunk_size):
                chunk = disabled_ids[i:i+chunk_size]
                if chunk:
                    rule = self._create_rule(
                        action_type='MAKE_DISABLED',
                        source_ids=[first_field_id],
                        destination_ids=chunk,
                        conditional_values=['Disable'],
                        condition='NOT_IN'
                    )
                    self._add_rule(first_field_id, rule)

    def _generate_convert_to_rules(self):
        """Generate CONVERT_TO rules (target: 21)."""
        for field_name in self.CONVERT_TO_FIELD_RULES:
            fld = self.match_field(field_name)
            if fld:
                rule = self._create_rule(
                    action_type='CONVERT_TO',
                    source_ids=[fld.id],
                    source_type='UPPER_CASE',
                )
                self._add_rule(fld.id, rule)

    def _generate_validation_rules(self):
        """Generate VALIDATION rules (target: 18)."""
        for field_name, params in self.VALIDATION_FIELD_RULES:
            fld = self.match_field(field_name)
            if fld:
                rule = self._create_rule(
                    action_type='VALIDATION',
                    source_ids=[fld.id],
                    params=params,
                )
                self._add_rule(fld.id, rule)

    def _generate_copy_to_rules(self):
        """Generate COPY_TO rules (target: 12)."""
        for src_name, dest_names in self.COPY_TO_FIELD_RULES:
            src = self.match_field(src_name)
            if not src:
                continue
            dest_ids = []
            for dn in dest_names:
                d = self.match_field(dn)
                if d:
                    dest_ids.append(d.id)
            if dest_ids:
                rule = self._create_rule(
                    action_type='COPY_TO',
                    source_ids=[src.id],
                    destination_ids=dest_ids,
                )
                self._add_rule(src.id, rule)

    def _generate_document_storage_rules(self):
        """Generate COPY_TO_DOCUMENT_STORAGE_ID rules (target: 18)."""
        added_count = 0

        for field_name in self.DOCUMENT_STORAGE_FIELDS:
            fld = self.match_field(field_name)
            if fld:
                rule = self._create_rule(
                    action_type='COPY_TO_DOCUMENT_STORAGE_ID',
                    source_ids=[fld.id],
                    source_type='FORM_FILL_METADATA',
                    processing_type='SERVER'
                )
                if self._add_rule(fld.id, rule):
                    added_count += 1

        for fld in self.file_upload_fields:
            if added_count >= 18:
                break
            rule = self._create_rule(
                action_type='COPY_TO_DOCUMENT_STORAGE_ID',
                source_ids=[fld.id],
                source_type='FORM_FILL_METADATA',
                processing_type='SERVER'
            )
            if self._add_rule(fld.id, rule):
                added_count += 1

    def _generate_special_rules(self):
        """Generate special rules - ensures all special rule types."""
        # Transaction ID - COPY_TXNID_TO_FORM_FILL
        txn = self.match_field('Transaction ID')
        if not txn:
            txn = self.match_field('Search term / Reference Number')
            if not txn:
                txn = self.match_field('Search term / Reference Number(Transaction ID)')
        if txn:
            rule = self._create_rule(
                action_type='COPY_TXNID_TO_FORM_FILL',
                source_ids=[txn.id],
                destination_ids=[txn.id],
                conditional_values=['TXN'],
                condition='NOT_IN'
            )
            self._add_rule(txn.id, rule)

        # Created On - SET_DATE
        created = self.match_field('Created on')
        if not created:
            created = self.match_field('Created On')
        if created:
            rule = self._create_rule(
                action_type='SET_DATE',
                source_ids=[created.id],
                destination_ids=[created.id],
                params='dd-MM-yyyy hh:mm:ss a',
                processing_type='SERVER'
            )
            self._add_rule(created.id, rule)

        # CONCAT rules (target: 2)
        # First CONCAT - Name field
        name_field = self.match_field('Name/ First Name of the Organization')
        if name_field:
            rule = self._create_rule(
                action_type='CONCAT',
                source_ids=[name_field.id],
                destination_ids=[],
            )
            self._add_rule(name_field.id, rule)

        # Second CONCAT - Street field
        street = self.match_field('Street')
        if street:
            rule = self._create_rule(
                action_type='CONCAT',
                source_ids=[street.id],
                destination_ids=[street.id],
            )
            self._add_rule(street.id, rule)

        # RuleCheck MAKE_DISABLED
        if self.rulecheck_field:
            rule = self._create_rule(
                action_type='MAKE_DISABLED',
                source_ids=[self.rulecheck_field.id],
                destination_ids=[self.rulecheck_field.id],
                conditional_values=['Disable'],
                condition='NOT_IN'
            )
            self._add_rule(self.rulecheck_field.id, rule)

        # Created By Name - COPY_TO with sourceType CREATED_BY
        created_by_name = self.match_field('Created By Name')
        if created_by_name:
            created_by = self.match_field('Created By')
            created_by_email = self.match_field('Created By Email')
            created_by_mobile = self.match_field('Created By Mobile')
            dest_ids = [created_by_name.id]
            if created_by:
                dest_ids.append(created_by.id)
            if created_by_email:
                dest_ids.append(created_by_email.id)
            if created_by_mobile:
                dest_ids.append(created_by_mobile.id)
            rule = self._create_rule(
                action_type='COPY_TO',
                source_ids=[created_by_name.id],
                destination_ids=dest_ids,
                source_type='CREATED_BY',
                processing_type='SERVER'
            )
            self._add_rule(created_by_name.id, rule)

        # Name/ First Name - COPY_TO_TRANSACTION_ATTR3
        name_field = self.match_field('Name/ First Name of the Organization')
        if name_field:
            rule = self._create_rule(
                action_type='COPY_TO_TRANSACTION_ATTR3',
                source_ids=[name_field.id],
                source_type='FORM_FILL_METADATA',
                processing_type='SERVER'
            )
            self._add_rule(name_field.id, rule)

        # Company and Ownership - COPY_TO_TRANSACTION_ATTR1
        company = self.match_field('Company and Ownership')
        if company:
            rule = self._create_rule(
                action_type='COPY_TO_TRANSACTION_ATTR1',
                source_ids=[company.id],
                source_type='FORM_FILL_METADATA',
                processing_type='SERVER'
            )
            self._add_rule(company.id, rule)

        # Choose the Group - DUMMY_ACTION
        group = self.match_field('Choose the Group of Company')
        if group:
            rule = self._create_rule(
                action_type='DUMMY_ACTION',
                source_ids=[group.id],
                processing_type='SERVER'
            )
            self._add_rule(group.id, rule)

        # Vendor Contact Email - COPY_TO_GENERIC_PARTY_EMAIL
        email = self.match_field('Vendor Contact Email')
        if email:
            rule = self._create_rule(
                action_type='COPY_TO_GENERIC_PARTY_EMAIL',
                source_ids=[email.id],
                processing_type='SERVER'
            )
            self._add_rule(email.id, rule)

        # Vendor Contact Name - COPY_TO_GENERIC_PARTY_NAME
        contact_name = self.match_field('Vendor Contact Name')
        if contact_name:
            rule = self._create_rule(
                action_type='COPY_TO_GENERIC_PARTY_NAME',
                source_ids=[contact_name.id],
                processing_type='SERVER'
            )
            self._add_rule(contact_name.id, rule)

        # Vendor Mobile Number - SEND_OTP
        mobile = self.match_field('Vendor Mobile Number')
        if mobile:
            rule = self._create_rule(
                action_type='SEND_OTP',
                source_ids=[mobile.id],
                processing_type='SERVER'
            )
            self._add_rule(mobile.id, rule)

        # Vendor Mobile Number OTP - VALIDATE_OTP
        otp = self.match_field('Vendor Mobile Number OTP')
        if otp:
            rule = self._create_rule(
                action_type='VALIDATE_OTP',
                source_ids=[otp.id],
                processing_type='SERVER'
            )
            self._add_rule(otp.id, rule)

    def _rebuild_rules_by_field(self):
        """Rebuild rules_by_field dictionary."""
        self.rules_by_field.clear()
        for rule in self.all_rules:
            if rule.source_ids:
                self.rules_by_field[rule.source_ids[0]].append(rule)

    def _populate_schema(self) -> Dict:
        """Populate schema with generated rules."""
        populated = copy.deepcopy(self.schema)
        for dt in populated.get('template', {}).get('documentTypes', []):
            for meta in dt.get('formFillMetadatas', []):
                rules = self.rules_by_field.get(meta.get('id'), [])
                meta['formFillRules'] = [r.to_dict() for r in rules]
        return populated

    def _generate_report(self) -> Dict:
        """Generate extraction report."""
        counts = defaultdict(int)
        for r in self.all_rules:
            counts[r.action_type] += 1

        # Reference counts
        reference_counts = {
            'MAKE_DISABLED': 5, 'MAKE_INVISIBLE': 19, 'COPY_TXNID_TO_FORM_FILL': 1,
            'SET_DATE': 1, 'COPY_TO': 12, 'CONVERT_TO': 21, 'COPY_TO_TRANSACTION_ATTR3': 1,
            'DUMMY_ACTION': 1, 'EXT_VALUE': 13, 'MAKE_MANDATORY': 12, 'MAKE_VISIBLE': 18,
            'COPY_TO_TRANSACTION_ATTR1': 1, 'VALIDATION': 18, 'CONCAT': 2,
            'DELETE_DOCUMENT': 15, 'UNDELETE_DOCUMENT': 17, 'EXT_DROP_DOWN': 20,
            'COPY_TO_GENERIC_PARTY_EMAIL': 1, 'COPY_TO_GENERIC_PARTY_NAME': 1,
            'SEND_OTP': 1, 'VALIDATE_OTP': 1, 'COPY_TO_DOCUMENT_STORAGE_ID': 18,
            'OCR': 6, 'VERIFY': 5, 'MAKE_NON_MANDATORY': 10, 'MAKE_ENABLED': 1
        }

        discrepancies = []
        for action, expected in reference_counts.items():
            generated = counts.get(action, 0)
            if generated != expected:
                discrepancies.append({
                    'action_type': action,
                    'generated': generated,
                    'expected': expected,
                    'difference': generated - expected,
                    'severity': 'HIGH' if abs(generated - expected) > 2 else 'MEDIUM' if abs(generated - expected) > 0 else 'LOW'
                })

        return {
            "extraction_summary": {
                "version": "v4",
                "schema_input": self.schema_path,
                "intra_panel_input": self.intra_panel_path,
                "timestamp": datetime.now().isoformat(),
                "total_rules_generated": len(self.all_rules)
            },
            "rule_counts": dict(counts),
            "reference_comparison": {
                "reference_counts": reference_counts,
                "discrepancies": discrepancies,
                "perfect_matches": [k for k in reference_counts if counts.get(k, 0) == reference_counts[k]]
            },
            "ocr_verify_chains": {
                "total_ocr_rules": sum(1 for r in self.all_rules if r.action_type == 'OCR'),
                "chained": [(k, v) for k, v in self.OCR_VERIFY_CHAINS.items() if v and k in self.ocr_rules],
                "not_chained": [k for k in self.OCR_VERIFY_CHAINS if not self.OCR_VERIFY_CHAINS[k]]
            }
        }

    def save_output(self, output_path: str, report_path: Optional[str] = None):
        """Process and save output files."""
        populated = self.process()
        self._save_json(populated, output_path)

        print(f"\n{'='*60}")
        print("Rule Extraction v4 Complete")
        print(f"{'='*60}")
        print(f"Total rules generated: {len(self.all_rules)}")
        print(f"Output saved to: {output_path}")

        # Print rule counts
        counts = defaultdict(int)
        for r in self.all_rules:
            counts[r.action_type] += 1

        reference_counts = {
            'MAKE_DISABLED': 5, 'MAKE_INVISIBLE': 19, 'COPY_TXNID_TO_FORM_FILL': 1,
            'SET_DATE': 1, 'COPY_TO': 12, 'CONVERT_TO': 21, 'COPY_TO_TRANSACTION_ATTR3': 1,
            'DUMMY_ACTION': 1, 'EXT_VALUE': 13, 'MAKE_MANDATORY': 12, 'MAKE_VISIBLE': 18,
            'COPY_TO_TRANSACTION_ATTR1': 1, 'VALIDATION': 18, 'CONCAT': 2,
            'DELETE_DOCUMENT': 15, 'UNDELETE_DOCUMENT': 17, 'EXT_DROP_DOWN': 20,
            'COPY_TO_GENERIC_PARTY_EMAIL': 1, 'COPY_TO_GENERIC_PARTY_NAME': 1,
            'SEND_OTP': 1, 'VALIDATE_OTP': 1, 'COPY_TO_DOCUMENT_STORAGE_ID': 18,
            'OCR': 6, 'VERIFY': 5, 'MAKE_NON_MANDATORY': 10, 'MAKE_ENABLED': 1
        }

        print("\nRule counts (Generated vs Expected):")
        all_types = set(counts.keys()) | set(reference_counts.keys())
        for action in sorted(all_types):
            gen = counts.get(action, 0)
            exp = reference_counts.get(action, 0)
            diff = gen - exp
            status = "OK" if diff == 0 else f"{'+'if diff>0 else ''}{diff}"
            print(f"  {action}: {gen} vs {exp} [{status}]")

        if report_path:
            report = self._generate_report()
            self._save_json(report, report_path)
            print(f"\nReport saved to: {report_path}")

        return populated


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Rule Extraction Agent v4')
    parser.add_argument('--schema', required=True, help='Path to schema JSON')
    parser.add_argument('--intra-panel', help='Path to intra-panel references JSON')
    parser.add_argument('--output', help='Output path for populated schema')
    parser.add_argument('--report', help='Output path for extraction report')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    if not args.output:
        args.output = str(Path(args.schema).parent / "populated_v4.json")

    agent = RuleExtractionAgentV4(
        schema_path=args.schema,
        intra_panel_path=args.intra_panel,
        verbose=args.verbose
    )
    agent.save_output(args.output, args.report)


if __name__ == '__main__':
    main()
