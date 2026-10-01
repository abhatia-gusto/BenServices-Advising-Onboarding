-- policies by account, restricted to cohort eff/exp dates
SELECT Id, Name, Benefit_Type__c, Carrier__r.Name, Waiting_Period__c, Contribution_Scheme_Type__c,
       Contribution_for_EEs__c, Contribution_for_Dependents__c, Coverage_Effective_Date__c,
       Expiration_Date__c, Is_Selected__c, Policy_Status__c, Is_Base__c, Account__c, SystemModstamp
FROM Policy__c
WHERE Account__c IN (:accts)
  AND (Coverage_Effective_Date__c IN (:ren) OR Expiration_Date__c IN (:dbef))
