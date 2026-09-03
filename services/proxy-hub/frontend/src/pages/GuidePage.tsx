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
      title: t("guide.step1.title"),
      body: t("guide.step1.body"),
      link: { label: t("Tenants"), path: "/console/tenants" },
    },
    {
      title: t("guide.step2.title"),
      body: t("guide.step2.body"),
      link: { label: t("Principals"), path: "/console/principals" },
    },
    {
      title: t("guide.step3.title"),
      body: t("guide.step3.body"),
      link: { label: t("Tenants"), path: "/console/tenants" },
    },
    {
      title: t("guide.step4.title"),
      body: t("guide.step4.body"),
      link: { label: t("Backends"), path: "/console/backends" },
    },
    {
      title: t("guide.step5.title"),
      body: t("guide.step5.body"),
      link: { label: t("Backends"), path: "/console/backends" },
    },
    {
      title: t("guide.step6.title"),
      body: t("guide.step6.body"),
      link: { label: t("Tenants"), path: "/console/tenants" },
    },
    {
      title: t("guide.step7.title"),
      body: t("guide.step7.body"),
      link: { label: t("Tenants"), path: "/console/tenants" },
    },
    {
      title: t("guide.step8.title"),
      body: t("guide.step8.body"),
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
          <h3>{t("guide.tip.title")}</h3>
          <p>{t("guide.tip.body")}</p>
        </li>
      </ol>
    </section>
  );
}
