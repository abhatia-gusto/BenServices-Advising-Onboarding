SELECT Id, Opportunity__c, DBA__c, Effective_Date__c, Policy_Renewal_Date__c, Benefit_Order__c, SystemModstamp
FROM QA_Sheet__c WHERE Opportunity__c IN (:ids)
