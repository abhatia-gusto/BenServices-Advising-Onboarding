-- recert tickets only (Escalation_Reason__c LIKE '%ecert%'); raw Notes__c sanitized by classify_notes.py
SELECT Id, Name, Status__c, Escalation_Reason__c, Escalation_Reason_Detail__c, Recert_Status__c,
       Close_Date__c, Closed_Date_Time__c, CreatedDate, Notes__c, Close_Reason__c, Opportunity__c, SystemModstamp
FROM Ticket__c WHERE Opportunity__c IN (:ids) AND Escalation_Reason__c LIKE '%ecert%'
