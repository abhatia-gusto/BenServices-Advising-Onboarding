-- cohort
SELECT Id, Name, AccountId, Account.Name, Account.ZP_Company_ID__c, Owner.Name,
       Advising_Blocked_Reason__c, Funding_Type_Status__c, Needs_Recertification__c,
       Offering_Selection_Deadline__c, Reason_for_Advising__c, Renewal_Date__c, Source_ID__c,
       Special_Enrollment__c, StageName, Stage_Detail__c, Submission_Deadline__c, SystemModstamp
FROM Opportunity
WHERE RecordType.Name = 'Benefits Renewal'
  AND StageName IN ('Recommendation Sent','Engaged','Alternatives Requested','ER Confirm')
  AND Renewal_Date__c >= :floor AND Renewal_Date__c <= :ceiling
