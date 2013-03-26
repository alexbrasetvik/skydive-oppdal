define(['handlebars.vm'], function(Handlebars) { return Handlebars.template(function (Handlebars,depth0,helpers,partials,data) {
  helpers = helpers || Handlebars.helpers;
  var buffer = "", stack1, foundHelper, functionType="function", escapeExpression=this.escapeExpression, self=this;

function program1(depth0,data) {
  
  var buffer = "", stack1, foundHelper;
  buffer += "\n<span class=\"slots\">";
  foundHelper = helpers.free_slots;
  if (foundHelper) { stack1 = foundHelper.call(depth0, {hash:{}}); }
  else { stack1 = depth0.free_slots; stack1 = typeof stack1 === functionType ? stack1() : stack1; }
  buffer += escapeExpression(stack1) + "</span> slots\n";
  return buffer;}

function program3(depth0,data) {
  
  
  return "\nFull\n";}

function program5(depth0,data) {
  
  var buffer = "", stack1, foundHelper;
  buffer += "\n        &mdash;\n        <span class=\"departure\">\n";
  foundHelper = helpers.departure_in_minutes;
  if (foundHelper) { stack1 = foundHelper.call(depth0, {hash:{}}); }
  else { stack1 = depth0.departure_in_minutes; stack1 = typeof stack1 === functionType ? stack1() : stack1; }
  buffer += escapeExpression(stack1) + " mins\n</span>\n        ";
  return buffer;}

  buffer += "<table>\n    <thead>\n    <tr>\n    <th colspan=\"3\">\n        <span class=\"plane\">";
  stack1 = depth0.plane;
  stack1 = stack1 == null || stack1 === false ? stack1 : stack1.name;
  stack1 = typeof stack1 === functionType ? stack1() : stack1;
  buffer += escapeExpression(stack1) + "</span>\n        <span class=\"load\">#";
  foundHelper = helpers.load_number;
  if (foundHelper) { stack1 = foundHelper.call(depth0, {hash:{}}); }
  else { stack1 = depth0.load_number; stack1 = typeof stack1 === functionType ? stack1() : stack1; }
  buffer += escapeExpression(stack1) + "</span>\n        &mdash;\n        <span class=\"slots_left\">\n";
  stack1 = depth0.has_free_slots;
  stack1 = helpers['if'].call(depth0, stack1, {hash:{},inverse:self.program(3, program3, data),fn:self.program(1, program1, data)});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n</span>\n        ";
  stack1 = depth0.should_have_departed;
  stack1 = helpers.unless.call(depth0, stack1, {hash:{},inverse:self.noop,fn:self.program(5, program5, data)});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n\n    </th>\n    </tr>\n    </thead>\n    <tbody class=\"invoices\"></tbody>\n</table>";
  return buffer;}

);});