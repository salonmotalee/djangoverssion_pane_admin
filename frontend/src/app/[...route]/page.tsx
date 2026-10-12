import { notFound } from "next/navigation";
import { Shell } from "@/components/shell";
import { Dashboard } from "@/components/dashboard";
import { Customers, CustomerDetail } from "@/components/customers";
import { UsersPage } from "@/components/users";
import { Activity, Alerts, Profile } from "@/components/account";
export default async function AdminPage({
  params,
}: {
  params: Promise<{ route: string[] }>;
}) {
  const { route } = await params;
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
