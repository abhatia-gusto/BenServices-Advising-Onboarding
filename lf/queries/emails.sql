-- nested Parent.Opportunity__c (NO alias — aliases are only legal in aggregates)
SELECT Parent.Opportunity__c, Incoming, Subject, TextBody, MessageDate FROM EmailMessage
WHERE Parent.Opportunity__c IN (:ids) AND Parent.RecordType.Name='Benefits Renewal Case'
ORDER BY Parent.Opportunity__c, MessageDate
