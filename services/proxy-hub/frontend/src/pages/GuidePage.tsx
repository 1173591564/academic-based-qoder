import { PageHeader } from "../components";
import { useI18n } from "../i18n";
import { navigate } from "../components";

interface GuideStep {
  title: string;
  body: string;
  link?: { label: string; path: string };
}

export function GuidePage() {
  const { t } = useI18n();
  const steps: GuideStep[] = [
    {
      title: t("1. Create a tenant"),
      body: t(
        "On Tenants, select New tenant and enter a stable slug and display name. The tenant is the isolation boundary for tools, quotas, and routes.",
      ),
      link: { label: t("Tenants"), path: "/console/tenants" },
    },
    {
      title: t("2. Add members"),
      body: t(
        "After a teammate signs in with OIDC, find their principal and add it from the tenant's Teams & memberships page. Teams are optional.",
      ),
      link: { label: t("Principals"), path: "/console/principals" },
    },
    {
      title: t("3. Configure tool policy and quota"),
      body: t(
        "On Policy, quota & route, allow only the required tools, set request and concurrency limits, and enable enforcement when ready.",
      ),
      link: { label: t("Tenants"), path: "/console/tenants" },
    },
    {
      title: t("4. Register a Scholar backend"),
      body: t(
        "On Backends, register the data plane URL, the corpus version reported by readiness, and a credential reference such as env:SCHOLAR_SERVICE_TOKEN.",
      ),
      link: { label: t("Backends"), path: "/console/backends" },
    },
    {
      title: t("5. Probe and activate"),
      body: t(
        "Probe the backend to verify readiness and the corpus version, then activate it. Changing the URL or corpus version requires another probe.",
      ),
      link: { label: t("Backends"), path: "/console/backends" },
    },
    {
      title: t("6. Bind the tenant route"),
      body: t(
        "On Policy, quota & route, select the active backend and corpus version, save the route, and activate it for the tenant.",
      ),
      link: { label: t("Tenants"), path: "/console/tenants" },
    },
    {
      title: t("7. Issue an enrolment code"),
      body: t(
        "On the tenant's Access page, select a member, choose tools within the policy allowlist, and issue a time-limited code. It is shown only once.",
      ),
      link: { label: t("Tenants"), path: "/console/tenants" },
    },
    {
      title: t("8. Connect a teammate"),
      body: t(
        "After installing scholar-dsh-bundle, the teammate runs scholar gateway-login --code <enrolment-code> to use the authorized tools through the gateway.",
      ),
    },
  ];
  return (
    <section>
      <PageHeader
        eyebrow={t("GUIDE")}
        title={t("Setup guide")}
        description={t(
          "Follow these steps to onboard a tenant from zero to a working DSH capability.",
        )}
      />
      <ol className="guide-list">
        {steps.map((step) => (
          <li className="panel guide-step" key={step.title}>
            <h3>{step.title}</h3>
            <p>{step.body}</p>
            {step.link ? (
              <button
                type="button"
                className="secondary-button"
                onClick={() => navigate(step.link!.path)}
              >
                {step.link.label} →
              </button>
            ) : null}
          </li>
        ))}
        <li className="panel guide-step" key="tip">
          <h3>{t("Daily operations")}</h3>
          <p>
            {t(
              "Use Audit for redacted call records and Usage for quota levels. Revoke enrolments or sessions when access changes, and probe a backend again after corpus updates.",
            )}
          </p>
        </li>
      </ol>
    </section>
  );
}
