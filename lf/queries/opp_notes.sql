SELECT Id, Notes__c, StageName, Funding_Type_Status__c FROM Opportunity WHERE Id IN (:ids)
