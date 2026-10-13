import { notFound } from "next/navigation";
import { Shell } from "@/components/shell";
import { Dashboard } from "@/components/dashboard";
import { Customers, CustomerDetail } from "@/components/customers";
import { UsersPage } from "@/components/users";
import { Activity, Alerts, Profile } from "@/components/account";
import { isPortalSlug } from "@/lib/routing";
import {
  OrganizationDashboard,
  OrganizationLogin,
} from "@/components/organization-portal";
import type { OrganizationPublic } from "@/lib/types";

async function getOrganization(slug: string): Promise<OrganizationPublic> {
  const origin = (
    process.env.DJANGO_API_ORIGIN || "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
  const response = await fetch(
    `${origin}/api/organizations/${encodeURIComponent(slug)}/public/`,
    { cache: "no-store" },
  );
  if (response.status === 404) notFound();
  if (!response.ok) throw new Error("ارتباط با مجموعه برقرار نشد.");
  return response.json();
}
export default async function AdminPage({
  params,
}: {
  params: Promise<{ route: string[] }>;
}) {
  const { route } = await params;
  if (
    isPortalSlug(route[0]) &&
    (route.length === 1 || (route.length === 2 && route[1] === "dashboard"))
  ) {
    const organization = await getOrganization(route[0]);
    return route.length === 1 ? (
      <OrganizationLogin organization={organization} />
    ) : (
      <OrganizationDashboard key={organization.slug} slug={organization.slug} />
    );
  }
  let content;
  if (route.length === 1) {
    switch (route[0]) {
      case "dashboard":
        content = <Dashboard />;
        break;
      case "customers":
        content = <Customers />;
        break;
      case "users":
        content = <UsersPage />;
        break;
      case "activity":
        content = <Activity />;
        break;
      case "alerts":
        content = <Alerts />;
        break;
      case "profile":
        content = <Profile />;
        break;
      default:
        notFound();
    }
  } else if (
    route.length === 2 &&
    route[0] === "customers" &&
    /^\d+$/.test(route[1])
  )
    content = <CustomerDetail id={Number(route[1])} />;
  else notFound();
  return <Shell>{content}</Shell>;
}
