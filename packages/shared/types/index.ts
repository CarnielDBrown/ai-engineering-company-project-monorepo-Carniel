export type Id = string;

export interface BaseEntity {
  id: Id;
  createdAt: string;
  updatedAt: string;
}

export type CountryCode = "US" | "GB";
export type ClinicStatus = "active" | "inactive";
export type AppointmentStatus = "requested" | "confirmed" | "completed" | "cancelled" | "no_show";
export type PatientLanguage = "English" | "Spanish";
export type PreferredTime = "morning" | "afternoon" | "evening";
export type ServiceType =
  | "Primary Care"
  | "Chronic Disease Management"
  | "Specialist Consultation"
  | "Preventive Health"
  | "Women's Health"
  | "Paediatric Care"
  | "Mental Health";
export type SortDirection = "asc" | "desc";

export interface Clinic extends BaseEntity {
  name: string;
  city: string;
  stateOrRegion: string;
  country: CountryCode;
  phone: string;
  openingHours: string[];
  latestEveningHour: number;
  status: ClinicStatus;
}

export interface Patient extends BaseEntity {
  firstName: string;
  lastName: string;
  dateOfBirth: string;
  email: string;
  phone: string;
  preferredLanguage: PatientLanguage;
  patientId?: string;
  hasInsurance: boolean;
  insuranceProvider?: string;
  insuranceMemberId?: string;
}

export interface Appointment extends BaseEntity {
  patientId: Id;
  clinicId: Id;
  serviceType: ServiceType;
  appointmentDate: string;
  preferredTime: PreferredTime;
  status: AppointmentStatus;
  estimatedCharge: number;
  noShowRiskScore?: number;
}

export interface PatientEnquiry extends BaseEntity {
  firstName: string;
  lastName: string;
  dateOfBirth: string;
  email: string;
  phone: string;
  preferredLanguage: PatientLanguage;
  preferredClinic: string;
  preferredDate: string;
  preferredTime: PreferredTime;
  serviceType: ServiceType;
  newPatient: boolean;
  hasInsurance: boolean;
  insuranceProvider?: string;
  insuranceMemberId?: string;
  patientId?: string;
  healthConcern: string;
  contactConsent: boolean;
}

export type StaffRole = "clinician" | "front_desk" | "administrator";

export interface StaffMember extends BaseEntity {
  firstName: string;
  lastName: string;
  email: string;
  role: StaffRole;
  clinicIds: Id[];
  active: boolean;
}

export interface Service extends BaseEntity {
  name: ServiceType;
  category: "primary_care" | "specialist" | "preventive" | "mental_health";
  description: string;
  startingPrice: number;
  active: boolean;
}

export interface FilterCriteria<T> {
  matches?: Partial<{ [Property in keyof T]: T[Property] }>;
  predicate?: (item: T) => boolean;
}

export interface SortCriterion<T> {
  field: keyof T;
  direction: SortDirection;
}

export interface AggregationReport {
  count: number;
  total: number;
  average: number;
  minimum: number | undefined;
  maximum: number | undefined;
}

export interface ValidationError {
  field: string;
  message: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
}

export interface ValidationOptions {
  referenceDate?: Date;
}

export const HEALTHCORE_US_CLINIC_NAMES: readonly string[] = [
  "HealthCore Austin Central",
  "HealthCore Austin North",
  "HealthCore San Antonio",
  "HealthCore Miami",
  "HealthCore Orlando",
  "HealthCore Atlanta",
];

export const SERVICE_TYPES: readonly ServiceType[] = [
  "Primary Care",
  "Chronic Disease Management",
  "Specialist Consultation",
  "Preventive Health",
  "Women's Health",
  "Paediatric Care",
  "Mental Health",
];

export * from "./queries";
export * from "./validation";
