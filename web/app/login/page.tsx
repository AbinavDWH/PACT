"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { UserRole, getRoleHome, setSession } from "../../lib/auth";



const ROLES: { value: UserRole; label: string; description: string; icon: string }[] = [
  {
    value: "admin",
    label: "Administrator",
    description: "Coordinate resources and manage the network",
    icon: "🛡️",
  },
  {
    value: "donor_group",
    label: "Donor Group",
    description: "Organization providing resources and aid",
    icon: "👥",
  },
  {
    value: "individual",
    label: "Individual",
    description: "Field worker or person in need of assistance",
    icon: "👤",
  },
];

export default function LoginPage() {
  const router = useRouter();
  const [selectedRole, setSelectedRole] = useState<UserRole | null>(null);
  const [orgId, setOrgId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = () => {
  if (!selectedRole) {
    setError("Please select a role");
    return;
  }
  if (!orgId.trim() || !displayName.trim()) {
    setError("Please fill in all fields");
    return;
  }

  setSession({
    role: selectedRole,
    organizationId: orgId.trim().toUpperCase(),
    displayName: displayName.trim(),
  });

  // CHANGE THIS LINE: redirect to role-specific home
  router.push(getRoleHome(selectedRole));
};

  return (
    <main className="min-h-screen bg-[#FFFAF3] flex items-center justify-center px-6 py-12">
      <div className="w-full max-w-2xl space-y-8">
        <header className="text-center">
          <h1 className="text-4xl font-bold text-[#2b1a0e]">Welcome to PACT</h1>
          <p className="mt-2 text-lg text-[#7c6a58]">Select your role to continue</p>
        </header>

        {/* Role Selection */}
        <div className="space-y-3">
          {ROLES.map((role) => (
            <button
              key={role.value}
              onClick={() => setSelectedRole(role.value)}
              className={`w-full rounded-xl border-2 p-6 text-left transition-all ${
                selectedRole === role.value
                  ? "border-[#F62440] bg-white shadow-lg"
                  : "border-[#FFE5BF] bg-white hover:border-[#F62440] hover:shadow-md"
              }`}
            >
              <div className="flex items-start gap-4">
                <span className="text-4xl">{role.icon}</span>
                <div className="flex-1">
                  <h3 className="text-lg font-bold text-[#2b1a0e]">{role.label}</h3>
                  <p className="text-sm text-[#7c6a58]">{role.description}</p>
                </div>
                {selectedRole === role.value && (
                  <span className="text-[#F62440] text-2xl">✓</span>
                )}
              </div>
            </button>
          ))}
        </div>

        {/* Details Form */}
        {selectedRole && (
          <div className="rounded-xl border border-[#FFE5BF] bg-white p-6 space-y-4">
            <h2 className="text-lg font-bold text-[#2b1a0e]">
              {selectedRole === "admin" && "Admin Setup"}
              {selectedRole === "donor_group" && "Donor Group Setup"}
              {selectedRole === "individual" && "Individual Setup"}
            </h2>

            <div>
              <label className="block text-sm font-semibold text-[#7c4a12] mb-1">
                Display Name
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder={
                  selectedRole === "admin"
                    ? "Your name as coordinator"
                    : selectedRole === "donor_group"
                    ? "Organization or group name"
                    : "Your name"
                }
                className="w-full rounded-lg border border-[#e3c9a8] px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#F62440]"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-[#7c4a12] mb-1">
                Organization ID
              </label>
              <input
                type="text"
                value={orgId}
                onChange={(e) => setOrgId(e.target.value.toUpperCase())}
                placeholder={
                  selectedRole === "admin"
                    ? "ADMIN01"
                    : selectedRole === "donor_group"
                    ? "NGO01, CSR02"
                    : "WORKER01"
                }
                className="w-full rounded-lg border border-[#e3c9a8] px-4 py-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#F62440]"
              />
            </div>

            {error && (
              <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              onClick={handleSubmit}
              className="w-full rounded-lg bg-[#F62440] px-6 py-3 text-lg font-bold text-white transition hover:opacity-90"
            >
              Continue
            </button>
          </div>
        )}
      </div>
    </main>
  );
}