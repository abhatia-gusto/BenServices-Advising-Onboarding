SELECT e.SFDC_EE_ID, e.NAME, e.EMAIL, e.SFDC_USER_ID, e.SUB_TEAM, e.STATUS,
       COALESCE(pe.NAME, e.MU_NAME) AS manager
FROM BI.GUSTO_EMPLOYEES e
LEFT JOIN BI.GUSTO_EMPLOYEES pe ON e.PE_SFDC_EE_ID=pe.SFDC_EE_ID AND pe.CURRENT_FLAG=TRUE
WHERE e.CURRENT_FLAG=TRUE  -- union-from-data: ALL statuses. STATUS col drives active-vs-former;
  -- build includes a former IC only if they have scored data in-window (worked-months kept).
  AND e.SUB_TEAM IN ('New Plan & Renewal Onboarding','Onboarding Advocacy') AND e.IS_PE=FALSE
